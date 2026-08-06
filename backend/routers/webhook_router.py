"""
routers/webhook_router.py — FastAPI Endpoint for GitHub Webhooks.

Exposes:
- POST /api/webhooks/github -> GitHub App event webhook listener
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Request, status
from services.webhook_service import WebhookService

logger = logging.getLogger("backend")

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post("/github", status_code=status.HTTP_200_OK)
async def handle_github_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    POST /api/webhooks/github

    GitHub App Webhook Ingestion Endpoint.

    Supported events:
    - ping
    - installation
    - installation_repositories
    - pull_request

    Security & Validation:
    - Verifies X-Hub-Signature-256 with HMAC-SHA256 digest
    - Deduplicates event processing using X-GitHub-Delivery
    - Records audit logs for compliance
    """
    return await WebhookService.process_webhook(
        request, background_tasks=background_tasks
    )
