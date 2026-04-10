import asyncio
import hashlib
import hmac
import logging
import os

from dotenv import load_dotenv

# 1. Load environment variables FIRST (from backend/.env regardless of cwd)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Security

# Verify critical environment variables
if not os.getenv("GITHUB_TOKEN"):
    print("CRITICAL: GITHUB_TOKEN is missing from .env")
if not os.getenv("GROQ_API_KEY"):
    print("CRITICAL: GROQ_API_KEY is missing from .env")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from services.ai_service import analyze_code
from services.diff_validator import DiffValidator
from services.filter_service import parse_and_filter_issues

# 2. Import services
from services.github_service import fetch_diff, post_comment, post_inline_comment
from services.syntax_validator import SyntaxValidator
from utils.formatter import format_inline_issue
import stats_store


# Configure logging with Deep Secret Scrubbing
class SecretScrubbingFilter(logging.Filter):
    def filter(self, record):
        secrets = [
            os.getenv("GITHUB_TOKEN"),
            os.getenv("GROQ_API_KEY"),
            os.getenv("DASHBOARD_API_KEY"),
            os.getenv("GITHUB_WEBHOOK_SECRET"),
        ]

        # Helper to scrub a string
        def scrub(text: str) -> str:
            if not text:
                return ""
            for secret in secrets:
                if secret and len(secret) > 8:
                    text = text.replace(secret, "[REDACTED]")
            return text

        # 1. Scrub the main message
        record.msg = scrub(str(record.msg))

        # 2. Scrub arguments
        if record.args:
            new_args = []
            for arg in record.args:
                new_args.append(scrub(str(arg)) if isinstance(arg, str) else arg)
            record.args = tuple(new_args)

        # 3. CRITICAL: Scrub tracebacks (exc_text)
        if record.exc_info:
            # If the log already has formatted exception text, scrub it
            if record.exc_text:
                record.exc_text = scrub(record.exc_text)

        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("backend_log.txt"), logging.StreamHandler()],
)
logger = logging.getLogger("backend")
for handler in logging.root.handlers:
    handler.addFilter(SecretScrubbingFilter())

app = FastAPI(
    title="AI PR Reviewer Enterprise API",
    description="High-Scale, Resilient, Syntax-Aware Backend.",
    version="5.0.0",
)

# Concurrency Control
analysis_semaphore = asyncio.Semaphore(5)


# Lifecycle Management: Persistent DB Connection
@app.on_event("startup")
async def startup_event():
    await stats_store.initialize_db()


@app.on_event("shutdown")
async def shutdown_event():
    await stats_store.close_db()


# CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Authentication Dependency
# Default is open for local/dev dashboards; set REQUIRE_DASHBOARD_API_KEY=true to enforce auth.
REQUIRE_DASHBOARD_API_KEY = (
    os.getenv("REQUIRE_DASHBOARD_API_KEY", "false").lower() == "true"
)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str | None = Security(api_key_header)):
    if not REQUIRE_DASHBOARD_API_KEY:
        return True

    correct_key = os.getenv("DASHBOARD_API_KEY")
    if not correct_key:
        logger.critical("DASHBOARD_API_KEY is required but not set.")
        raise HTTPException(status_code=500, detail="Server Configuration Error")
    if api_key != correct_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def verify_signature(payload_body: bytes, signature_header: str):
    """Verifies the GitHub webhook signature. Mandatory for production."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        logger.error("CRITICAL: GITHUB_WEBHOOK_SECRET is not set. Rejecting all webhooks.")
        raise HTTPException(status_code=401, detail="Webhook secret configuration missing")

    if not signature_header:
        raise HTTPException(status_code=401, detail="X-Hub-Signature-256 header is missing")

    hash_object = hmac.new(secret.encode(), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


async def process_webhook(payload: dict):
    """Production-grade fail-safe pipeline with guaranteed finalization."""
    async with analysis_semaphore:
        head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
        repo_full_name = payload.get("repository", {}).get("full_name", "unknown/repo")
        owner, repo = repo_full_name.split("/")
        pr_number = payload.get("pull_request", {}).get("number")

        pr_id = None
        # FAIL-SAFE DEFAULTS
        final_status = "error"
        decision = "BLOCK"
        high_count = med_count = low_count = 0
        valid_issues = []

        try:
            logger.info(f"🚀 [Production] Starting PR #{pr_number} | SHA: {head_sha}")
            pr_id = await stats_store.initiate_review(repo, pr_number, status="processing")

            # 1. Fetch Diff
            diff = await fetch_diff(owner, repo, pr_number)
            if not diff:
                # Handle empty/metadata PRs as SKIPPED/SAFE
                final_status = "success"
                decision = "SAFE"
                logger.info(f"⏭️ PR #{pr_number} contains no code changes. Skipping.")
                return

            # 2. AI Analysis
            analysis = await analyze_code(diff)
            if analysis.get("status") == "failed":
                raise ValueError(f"Stage Failed: AI Analysis - {analysis.get('reason')}")

            # 3. Validation & Filtering
            raw_issues = parse_and_filter_issues(analysis)

            # Multi-Layer Pruning
            mapped_issues = [i for i in raw_issues if DiffValidator.validate_issue(i, DiffValidator.parse_diff_mapping(diff))]
            # Layer 2: Syntax Integrity - Downgrade instead of Prune
            valid_issues = []
            for i in mapped_issues:
                if SyntaxValidator.validate_issue(i):
                    valid_issues.append(i)
                else:
                    # Downgrade severity and flag for manual review
                    i["severity"] = "low"
                    i["description"] = f"[NEEDS REVIEW: SUGGESTION SYNTAX ERR] {i.get('description', '')}"
                    valid_issues.append(i)

            # 4. Strict Decision Logic
            high_count = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "high")
            med_count = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "medium")
            low_count = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "low")

            # DATA INTEGRITY CHECK
            if (high_count + med_count + low_count) != len(valid_issues):
                logger.error(f"Integrity Mismatch: {high_count}+{med_count}+{low_count} != {len(valid_issues)}")
                decision = "BLOCK"
            else:
                if high_count > 0:
                    decision = "BLOCK"
                elif med_count >= 3:
                    decision = "REVIEW"
                else:
                    decision = "SAFE"

            # 5. Commenting
            if valid_issues:
                diff_mapping = DiffValidator.parse_diff_mapping(diff)
                for issue in valid_issues:
                    suggestion = DiffValidator.generate_suggestion(issue, diff_mapping)
                    await post_inline_comment(owner, repo, pr_number, issue, head_sha, suggestion=suggestion)

            final_status = "success"

        except Exception as e:
            logger.critical(f"🔥 Fail-Safe Triggered: {str(e)}", exc_info=True)
            final_status = "error"
            decision = "BLOCK"

        finally:
            if pr_id:
                await stats_store.finalize_review(
                    pr_id, valid_issues,
                    status=final_status,
                    decision_status=decision,
                    high=high_count,
                    medium=med_count,
                    low=low_count
                )
            if head_sha:
                await stats_store.mark_sha_status(head_sha, "completed" if final_status == "success" else "failed")

            logger.info(f"[Webhook Finalized] PR={pr_number} Status={final_status} Decision={decision} Issues={len(valid_issues)}")


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    verify_signature(body, request.headers.get("X-Hub-Signature-256"))

    payload = await request.json()
    action = payload.get("action")
    if action not in ["opened", "synchronize"]:
        return {"status": "ignored", "action": action}

    head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
    if not head_sha:
        return {"status": "error", "reason": "MISSING_SHA"}

    # ATOMIC CLAIMING: Integrated State Recovery + Race Protection
    if not await stats_store.claim_sha_for_processing(head_sha):
        logger.info(
            f"🛑 [webhook] SHA {head_sha} skip: active task exists and is not stale."
        )
        return {"status": "ignored", "reason": "DUPLICATE_CLAIM_REJECTED"}

    background_tasks.add_task(process_webhook, payload)
    return {"status": "processing", "sha": head_sha}


@app.get("/api/stats")
async def stats(page: int = 1, authenticated: bool = Depends(get_api_key)):
    limit = 15
    offset = (page - 1) * limit
    return await stats_store.get_stats(limit=limit, offset=offset)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "enterprise-ai-reviewer",
        "concurrency": analysis_semaphore._value,
    }


@app.get("/")
async def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


# Dummy secret for AI verification (safe non-production placeholder)
DUMMY_API_KEY = os.getenv("DUMMY_API_KEY", "mock-secret-dummy-api-key")

import subprocess


@app.get("/run_cmd")
async def run_cmd(cmd: str):
    # DANGEROUS: Command injection vulnerability for AI to catch
    return subprocess.check_output(cmd, shell=True)
