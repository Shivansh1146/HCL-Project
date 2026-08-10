"""
services/webhook_service.py — Enterprise GitHub Webhook Infrastructure Service.

Responsibilities:
1. Verify X-Hub-Signature-256 using HMAC-SHA256 and GITHUB_WEBHOOK_SECRET.
2. Validate presence of required GitHub headers (X-GitHub-Event, X-GitHub-Delivery, X-Hub-Signature-256).
3. Handle event deduplication via X-GitHub-Delivery tracking.
4. Process supported webhook events (ping, installation, installation_repositories, pull_request).
5. Log events and write structured audit records via AuditService.
"""

import hmac
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fastapi import Request, HTTPException, status, BackgroundTasks
from services.audit_service import AuditService
from auth.models import AuditSeverity
from auth.store import is_delivery_processed, record_webhook_delivery

logger = logging.getLogger("backend")

SUPPORTED_EVENTS = {
    "ping",
    "installation",
    "installation_repositories",
    "pull_request",
}


class WebhookService:
    """Service encapsulating GitHub Webhook signature validation and event handling."""

    @staticmethod
    def verify_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
        """
        Verifies X-Hub-Signature-256 header against payload body and webhook secret.

        GitHub sends header: sha256=<hex_digest>
        """
        if not signature_header or not secret:
            return False

        if not signature_header.startswith("sha256="):
            return False

        expected_sig = signature_header[7:]  # strip 'sha256='
        mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
        computed_sig = mac.hexdigest()

        return hmac.compare_digest(computed_sig, expected_sig)

    @classmethod
    async def process_webhook(cls, request: Request, background_tasks: Optional[BackgroundTasks] = None) -> Dict[str, Any]:
        """
        Main entry point for processing incoming GitHub webhook requests.

        Workflow:
        1. Read raw body payload.
        2. Extract & validate headers (X-Hub-Signature-256, X-GitHub-Event, X-GitHub-Delivery).
        3. Verify HMAC signature against GITHUB_WEBHOOK_SECRET.
        4. Validate JSON payload structure.
        5. Check and record delivery ID to prevent duplicate execution.
        6. Log and audit event processing.
        7. Return structured processing summary.
        """
        secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
        signature_header = request.headers.get("X-Hub-Signature-256", "")
        event_type = request.headers.get("X-GitHub-Event", "")
        delivery_id = request.headers.get("X-GitHub-Delivery", "")

        # 1. Header Validation
        if not signature_header:
            logger.warning("❌ [WEBHOOK] Missing X-Hub-Signature-256 header.")
            await AuditService.log_event(
                action="WEBHOOK_REJECTED",
                severity=AuditSeverity.WARNING,
                details={"reason": "Missing X-Hub-Signature-256 header", "event": event_type},
                request=request,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Hub-Signature-256 header.",
            )

        if not event_type:
            logger.warning("❌ [WEBHOOK] Missing X-GitHub-Event header.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing X-GitHub-Event header.",
            )

        # 2. Raw Body Read
        try:
            body_bytes = await request.body()
        except Exception as e:
            logger.error(f"❌ [WEBHOOK] Failed to read request body: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not read request body.",
            )

        # 3. Signature Verification
        if secret and not cls.verify_signature(body_bytes, signature_header, secret):
            logger.warning("❌ [WEBHOOK] Invalid HMAC signature.")
            await AuditService.log_event(
                action="WEBHOOK_UNAUTHORIZED",
                severity=AuditSeverity.WARNING,
                details={
                    "reason": "Invalid X-Hub-Signature-256 signature",
                    "event": event_type,
                    "delivery_id": delivery_id,
                },
                request=request,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-Hub-Signature-256 webhook signature.",
            )

        # 4. JSON Payload Parsing
        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning(f"❌ [WEBHOOK] Invalid JSON payload: {str(exc)}")
            await AuditService.log_event(
                action="WEBHOOK_BAD_PAYLOAD",
                severity=AuditSeverity.ERROR,
                details={"reason": "Invalid JSON", "event": event_type, "error": str(exc)},
                request=request,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload.",
            )

        # 5. Deduplication Check via X-GitHub-Delivery
        if delivery_id:
            already_processed = await is_delivery_processed(delivery_id)
            if already_processed:
                logger.info(f"ℹ️ [WEBHOOK] Duplicate delivery detected: {delivery_id}. Skipping.")
                await AuditService.log_event(
                    action="WEBHOOK_DUPLICATE_SKIPPED",
                    severity=AuditSeverity.INFO,
                    details={"delivery_id": delivery_id, "event": event_type},
                    request=request,
                )
                return {
                    "status": "ignored",
                    "reason": "duplicate_delivery",
                    "delivery_id": delivery_id,
                    "event": event_type,
                }

        # 6. Event Processing & Routing
        action = payload.get("action")
        logger.info(f"⚓ [WEBHOOK] Event='{event_type}' Action='{action}' Delivery='{delivery_id}'")

        result = await cls._handle_event(
            event_type, action, payload, delivery_id, request, background_tasks=background_tasks
        )

        # 7. Record Delivery GUID
        if delivery_id:
            await record_webhook_delivery(delivery_id, event_type, action)

        return result

    @classmethod
    async def _handle_event(
        cls,
        event_type: str,
        action: Optional[str],
        payload: Dict[str, Any],
        delivery_id: str,
        request: Request,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> Dict[str, Any]:
        """Dispatches event types to appropriate loggers / handlers."""

        if event_type not in SUPPORTED_EVENTS:
            logger.info(f"ℹ️ [WEBHOOK] Unhandled event type '{event_type}' received.")
            await AuditService.log_event(
                action="WEBHOOK_UNHANDLED_EVENT",
                severity=AuditSeverity.INFO,
                details={"event": event_type, "action": action, "delivery_id": delivery_id},
                request=request,
            )
            return {
                "status": "ignored",
                "reason": f"unhandled event type: {event_type}",
                "event": event_type,
                "delivery_id": delivery_id,
            }

        # Handle specific supported events
        if event_type == "ping":
            zen = payload.get("zen", "")
            hook_id = payload.get("hook_id")
            logger.info(f"🟢 [WEBHOOK:PING] Zen: '{zen}' Hook ID: {hook_id}")
            await AuditService.log_event(
                action="WEBHOOK_PING",
                severity=AuditSeverity.INFO,
                details={"zen": zen, "hook_id": hook_id, "delivery_id": delivery_id},
                request=request,
            )
            return {
                "status": "ok",
                "event": "ping",
                "zen": zen,
                "delivery_id": delivery_id,
            }

        elif event_type == "installation":
            inst_data = payload.get("installation", {})
            inst_id = inst_data.get("id")
            account = inst_data.get("account", {}).get("login", "unknown")
            logger.info(f"📦 [WEBHOOK:INSTALLATION] Action='{action}' InstID={inst_id} Account='{account}'")
            await AuditService.log_event(
                action=f"WEBHOOK_INSTALLATION_{action.upper() if action else 'EVENT'}",
                entity_type="installation",
                entity_id=str(inst_id) if inst_id else None,
                severity=AuditSeverity.INFO,
                details={"action": action, "account": account, "delivery_id": delivery_id},
                request=request,
            )
            return {
                "status": "ok",
                "event": "installation",
                "action": action,
                "installation_id": inst_id,
                "delivery_id": delivery_id,
            }

        elif event_type == "installation_repositories":
            inst_data = payload.get("installation", {})
            inst_id = inst_data.get("id")
            repos_added = [r.get("full_name") for r in payload.get("repositories_added", [])]
            repos_removed = [r.get("full_name") for r in payload.get("repositories_removed", [])]
            logger.info(
                f"📚 [WEBHOOK:INSTALLATION_REPOS] Action='{action}' InstID={inst_id} "
                f"Added={len(repos_added)} Removed={len(repos_removed)}"
            )
            await AuditService.log_event(
                action=f"WEBHOOK_INSTALLATION_REPOS_{action.upper() if action else 'EVENT'}",
                entity_type="installation",
                entity_id=str(inst_id) if inst_id else None,
                severity=AuditSeverity.INFO,
                details={
                    "action": action,
                    "added": repos_added,
                    "removed": repos_removed,
                    "delivery_id": delivery_id,
                },
                request=request,
            )
            return {
                "status": "ok",
                "event": "installation_repositories",
                "action": action,
                "installation_id": inst_id,
                "added_count": len(repos_added),
                "removed_count": len(repos_removed),
                "delivery_id": delivery_id,
            }

        elif event_type == "pull_request":
            from services.pr_service import PRService
            from auth.store import is_repo_whitelisted
            
            pr_data = payload.get("pull_request", {})
            pr_number = pr_data.get("number")
            repo_name = payload.get("repository", {}).get("full_name", "")
            sender = payload.get("sender", {}).get("login", "")
            
            # Check if repository is whitelisted/selected for AI review
            if repo_name and not await is_repo_whitelisted(repo_name):
                logger.info(
                    f"🚫 [WEBHOOK:PULL_REQUEST] Repository '{repo_name}' is not in selected repositories list. Ignoring PR #{pr_number}."
                )
                await AuditService.log_event(
                    action="WEBHOOK_PR_REPOSITORY_NOT_SELECTED",
                    entity_type="pull_request",
                    entity_id=f"{repo_name}#{pr_number}",
                    severity=AuditSeverity.WARNING,
                    details={
                        "action": action,
                        "pr_number": pr_number,
                        "repository": repo_name,
                        "reason": "REPOSITORY_NOT_SELECTED",
                        "delivery_id": delivery_id,
                    },
                    request=request,
                )
                return {
                    "status": "ignored",
                    "reason": "REPOSITORY_NOT_SELECTED",
                    "repository": repo_name,
                    "pr_number": pr_number,
                    "delivery_id": delivery_id,
                }
            
            logger.info(
                f"🔀 [WEBHOOK:PULL_REQUEST] Action='{action}' PR #{pr_number} in '{repo_name}' by '{sender}'"
            )
            await AuditService.log_event(
                action=f"WEBHOOK_PULL_REQUEST_{action.upper() if action else 'EVENT'}",
                entity_type="pull_request",
                entity_id=f"{repo_name}#{pr_number}",
                severity=AuditSeverity.INFO,
                details={
                    "action": action,
                    "pr_number": pr_number,
                    "repository": repo_name,
                    "sender": sender,
                    "delivery_id": delivery_id,
                },
                request=request,
            )

            # Delegate to PR processing service (upserts into DB and dispatches AI review)
            logger.info(f"🔄 [WEBHOOK:PULL_REQUEST] Calling PRService.process_pull_request_event()")
            
            res = await PRService.process_pull_request_event(
                payload, delivery_id, background_tasks=background_tasks
            )
            
            logger.info(f"✅ [WEBHOOK:PULL_REQUEST] PRService returned: {res.get('status')}")
            logger.info(f"✅ [WEBHOOK:PULL_REQUEST] AI review dispatched: {res.get('ai_review_dispatched')}")
            res["delivery_id"] = delivery_id
            return res

        return {"status": "ok", "event": event_type, "delivery_id": delivery_id}
