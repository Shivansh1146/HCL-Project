"""
tests/test_webhook.py — Unit & Integration tests for GitHub Webhook Infrastructure.

Tests cover:
1. Valid HMAC-SHA256 signature verification.
2. Invalid signature rejection (401 Unauthorized).
3. Missing signature header rejection (401 Unauthorized).
4. Missing X-GitHub-Event header rejection (400 Bad Request).
5. Invalid JSON body handling (400 Bad Request).
6. 'ping' webhook event processing.
7. 'installation' webhook event processing.
8. 'installation_repositories' webhook event processing.
9. 'pull_request' webhook event processing.
10. Duplicate delivery prevention via X-GitHub-Delivery header.
"""

import asyncio
import hmac
import hashlib
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from main import app
from auth.store import initialize_auth_db

WEBHOOK_SECRET = "test_webhook_secret_12345"


def setup_module(module):
    """Initializes Auth DB synchronously before test suite execution."""
    asyncio.run(initialize_auth_db())


def compute_signature(payload_bytes: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Computes valid sha256 signature for test payload."""
    mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


class TestWebhookInfrastructure:
    """Test suite for Phase 1.6 GitHub Webhook Infrastructure."""

    def test_webhook_valid_ping(self, monkeypatch):
        """Test valid ping event with correct HMAC signature."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        payload = {
            "zen": "Design for failure.",
            "hook_id": 12345678,
            "hook": {"type": "App", "id": 12345678, "active": True},
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = compute_signature(payload_bytes)
        delivery_id = str(uuid.uuid4())

        headers = {
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": delivery_id,
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        response = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["event"] == "ping"
        assert data["zen"] == "Design for failure."
        assert data["delivery_id"] == delivery_id

    def test_webhook_invalid_signature(self, monkeypatch):
        """Test webhook with wrong signature secret -> HTTP 401."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        payload = {"zen": "Testing invalid signature."}
        payload_bytes = json.dumps(payload).encode("utf-8")
        invalid_signature = compute_signature(payload_bytes, secret="wrong_secret")
        delivery_id = str(uuid.uuid4())

        headers = {
            "X-Hub-Signature-256": invalid_signature,
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": delivery_id,
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        response = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)

        assert response.status_code == 401
        assert "Invalid X-Hub-Signature-256" in response.json()["detail"]

    def test_webhook_missing_signature(self, monkeypatch):
        """Test webhook missing X-Hub-Signature-256 header -> HTTP 401."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        payload = {"zen": "Testing missing signature."}
        payload_bytes = json.dumps(payload).encode("utf-8")

        headers = {
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        response = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)

        assert response.status_code == 401
        assert "Missing X-Hub-Signature-256" in response.json()["detail"]

    def test_webhook_missing_event_header(self, monkeypatch):
        """Test webhook missing X-GitHub-Event header -> HTTP 400."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        payload = {"zen": "Testing missing event header."}
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = compute_signature(payload_bytes)

        headers = {
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        response = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)

        assert response.status_code == 400
        assert "Missing X-GitHub-Event" in response.json()["detail"]

    def test_webhook_invalid_json_payload(self, monkeypatch):
        """Test invalid JSON body -> HTTP 400."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        invalid_body = b"{ bad_json: true, "
        signature = compute_signature(invalid_body)

        headers = {
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        response = client.post("/api/webhooks/github", content=invalid_body, headers=headers)

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_webhook_installation_event(self, monkeypatch):
        """Test installation created event handling."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        payload = {
            "action": "created",
            "installation": {
                "id": 987654,
                "account": {"login": "Shivansh1146", "type": "User"},
            },
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = compute_signature(payload_bytes)
        delivery_id = str(uuid.uuid4())

        headers = {
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "installation",
            "X-GitHub-Delivery": delivery_id,
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        response = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["event"] == "installation"
        assert data["action"] == "created"
        assert data["installation_id"] == 987654

    def test_webhook_installation_repositories_event(self, monkeypatch):
        """Test installation_repositories added event handling."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        payload = {
            "action": "added",
            "installation": {"id": 987654},
            "repositories_added": [{"id": 101, "full_name": "Shivansh1146/repo1"}],
            "repositories_removed": [],
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = compute_signature(payload_bytes)
        delivery_id = str(uuid.uuid4())

        headers = {
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "installation_repositories",
            "X-GitHub-Delivery": delivery_id,
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        response = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["event"] == "installation_repositories"
        assert data["action"] == "added"
        assert data["added_count"] == 1
        assert data["removed_count"] == 0

    def test_webhook_pull_request_event(self, monkeypatch):
        """Test pull_request opened event handling."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        payload = {
            "action": "opened",
            "number": 42,
            "pull_request": {"number": 42, "title": "Feat: Add new API endpoint"},
            "repository": {"full_name": "Shivansh1146/HCL-Project"},
            "sender": {"login": "Shivansh1146"},
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = compute_signature(payload_bytes)
        delivery_id = str(uuid.uuid4())

        headers = {
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        response = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "processed")
        assert data["event"] == "pull_request" or data.get("pr_number") == 42
        assert data["action"] == "opened"
        assert data["pr_number"] == 42
        assert data["repository"] == "Shivansh1146/HCL-Project"

    def test_webhook_duplicate_delivery(self, monkeypatch):
        """Test deduplication: sending identical X-GitHub-Delivery GUID twice."""
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", WEBHOOK_SECRET)
        payload = {"zen": "Testing deduplication."}
        payload_bytes = json.dumps(payload).encode("utf-8")
        signature = compute_signature(payload_bytes)
        delivery_id = str(uuid.uuid4())

        headers = {
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": delivery_id,
            "Content-Type": "application/json",
        }

        client = TestClient(app)
        # First delivery -> processed
        res1 = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)
        assert res1.status_code == 200
        assert res1.json()["status"] == "ok"

        # Second delivery (duplicate GUID) -> skipped
        res2 = client.post("/api/webhooks/github", content=payload_bytes, headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "ignored"
        assert data2["reason"] == "duplicate_delivery"
