"""
tests/test_audit_service.py — Enterprise unit tests for AuditService.
"""
import pytest
import asyncio
import json
import os
import tempfile

test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["TEST_DB_PATH"] = test_db_file

from auth.store import initialize_auth_db, get_audit_logs_for_user, upsert_user
from services.audit_service import AuditService
from auth.models import AuditSeverity


def test_audit_service_structured_log_and_retrieve():
    async def _test():
        await initialize_auth_db()

        # Create dummy user
        user = await upsert_user(github_id=777, login="audit_user")

        # Log structured audit event
        await AuditService.log_event(
            action="REPO_ENABLE",
            user_id=user.id,
            entity_type="Repository",
            entity_id="101",
            severity=AuditSeverity.WARNING,
            details={"repo": "Shivansh1146/hcl-project", "action": "enabled"},
            request_id="req-12345",
            trace_id="trace-abc"
        )

        # Fetch audit logs
        logs = await get_audit_logs_for_user(user.id)
        assert len(logs) == 1
        log = logs[0]
        assert log.action == "REPO_ENABLE"
        assert log.entity_type == "Repository"
        assert log.entity_id == "101"
        assert log.severity == AuditSeverity.WARNING
        assert log.request_id == "req-12345"
        assert log.trace_id == "trace-abc"

        details_parsed = json.loads(log.details_json)
        assert details_parsed["repo"] == "Shivansh1146/hcl-project"

    asyncio.run(_test())
