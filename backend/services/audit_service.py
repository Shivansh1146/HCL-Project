"""
services/audit_service.py — Enterprise Audit Logging Service.

Provides single-responsibility methods for recording compliance events with rich context:
- request_id & trace_id support
- entity_type and entity_id linking
- structured details_json payload
- AuditSeverity classification (INFO, WARNING, ERROR, CRITICAL)
- Client IP & User-Agent capture
"""
import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import Request

from auth.store import create_audit_log
from auth.models import AuditSeverity

logger = logging.getLogger("backend")


class AuditService:
    """Enterprise audit logger encapsulating security event persistence."""

    @staticmethod
    async def log_event(
        action: str,
        user_id: Optional[int] = None,
        request: Optional[Request] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> None:
        """Asynchronously writes a structured enterprise audit log entry."""
        ip_address = None
        user_agent = None

        if request:
            client = request.client
            ip_address = client.host if client else None
            user_agent = request.headers.get("User-Agent")
            if not request_id:
                request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
            if not trace_id:
                trace_id = request.headers.get("X-Trace-ID", request_id)

        try:
            await create_audit_log(
                action=action,
                user_id=user_id,
                request_id=request_id,
                trace_id=trace_id,
                entity_type=entity_type,
                entity_id=entity_id,
                severity=severity.value if isinstance(severity, AuditSeverity) else severity,
                details_json=details,
                ip_address=ip_address,
                user_agent=user_agent
            )
            logger.info(
                f"🛡️ [AUDIT] action='{action}' severity='{severity}' user_id={user_id} "
                f"entity={entity_type}:{entity_id} request_id={request_id}"
            )
        except Exception as e:
            logger.error(f"Failed to record enterprise audit log: {str(e)}", exc_info=True)
