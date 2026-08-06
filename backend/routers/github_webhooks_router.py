"""GitHub App webhook ingress: verification, auditing, and idempotency only."""

import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request, status

from auth.store import record_github_webhook_delivery

logger = logging.getLogger("backend")
router = APIRouter(prefix="/api/webhooks", tags=["GitHub Webhooks"])
SUPPORTED_EVENTS = {"ping", "installation", "installation_repositories", "pull_request"}


def _signature_is_valid(payload: bytes, signature: str) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook secret is not configured.",
        )
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature)


@router.post("/github", status_code=status.HTTP_200_OK)
async def receive_github_webhook(request: Request) -> dict[str, object]:
    """Verify and persist supported GitHub deliveries; no review work is dispatched."""
    raw_payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _signature_is_valid(raw_payload, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid GitHub webhook signature.")

    event = request.headers.get("X-GitHub-Event", "")
    if event not in SUPPORTED_EVENTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported GitHub webhook event: {event or 'missing'}")
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON webhook payload.") from exc

    payload_hash = hashlib.sha256(raw_payload).hexdigest()
    delivery_id = request.headers.get("X-GitHub-Delivery", payload_hash)
    action = payload.get("action") if isinstance(payload, dict) else None
    installation = payload.get("installation", {}) if isinstance(payload, dict) else {}
    installation_id = str(installation.get("id", "")) if isinstance(installation, dict) else ""
    accepted = await record_github_webhook_delivery(
        delivery_id=delivery_id,
        event=event,
        payload_sha256=payload_hash,
        action=action if isinstance(action, str) else None,
        installation_id=installation_id or None,
        request=request,
    )
    if not accepted:
        logger.info("GitHub webhook duplicate ignored: delivery_id=%s event=%s", delivery_id, event)
        return {"status": "duplicate", "event": event, "delivery_id": delivery_id}

    logger.info("GitHub webhook accepted: delivery_id=%s event=%s action=%s", delivery_id, event, action)
    return {"status": "accepted", "event": event, "delivery_id": delivery_id}
