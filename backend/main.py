import logging
import os
import hmac
import hashlib
import asyncio
from dotenv import load_dotenv

# 1. Load environment variables FIRST
load_dotenv()

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# 2. Import services
from services.github_service import fetch_diff, post_comment, post_inline_comment
from services.ai_service import analyze_code
from services.filter_service import parse_and_filter_issues
from services.diff_validator import DiffValidator
from services.syntax_validator import SyntaxValidator
from stats_store import record_review, get_stats, initialize_db, close_db, is_sha_processed, mark_sha_status, claim_sha_for_processing, initiate_review, finalize_review

# Configure logging with Deep Secret Scrubbing
class SecretScrubbingFilter(logging.Filter):
    def filter(self, record):
        secrets = [
            os.getenv("GITHUB_TOKEN"),
            os.getenv("GROQ_API_KEY"),
            os.getenv("DASHBOARD_API_KEY"),
            os.getenv("GITHUB_WEBHOOK_SECRET")
        ]

        # Helper to scrub a string
        def scrub(text: str) -> str:
            if not text: return ""
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
    handlers=[
        logging.FileHandler("backend_log.txt", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("backend")
for handler in logging.root.handlers:
    handler.addFilter(SecretScrubbingFilter())

app = FastAPI(
    title="AI PR Reviewer Enterprise API",
    description="High-Scale, Resilient, Syntax-Aware Backend.",
    version="5.0.0"
)

# Concurrency Control
analysis_semaphore = asyncio.Semaphore(5)

# Lifecycle Management: Persistent DB Connection
@app.on_event("startup")
async def startup_event():
    await initialize_db()

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()

# CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Authentication Dependency - FAIL CLOSED
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def get_api_key():
    """Bypassing authentication as requested by the user."""
    return True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def verify_signature(payload_body: bytes, signature_header: str):
    """Verifies the GitHub webhook signature."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        logger.error("GITHUB_WEBHOOK_SECRET is not set in .env")
        return

    if not signature_header:
        raise HTTPException(status_code=401, detail="X-Hub-Signature-256 header is missing")

    hash_object = hmac.new(secret.encode(), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

async def process_webhook(payload: dict):
    """Enterprise backgroud task with Atomic State Protection and Syntax Validation."""
    async with analysis_semaphore:
        head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
        repo_full_name = payload.get("repository", {}).get("full_name", "unknown/repo")
        owner, repo = repo_full_name.split("/")
        pr_number = payload.get("pull_request", {}).get("number")

        pr_id = None
        try:
            logger.info(f"🚀 [Enterprise] Starting PR #{pr_number} | SHA: {head_sha}")

            # ATOMIC INITIATION: Record intent in Dashboard before any side effects
            pr_id = await initiate_review(repo, pr_number, status="fetching_diff")

            # 1. Fetch Diff
            diff = await fetch_diff(owner, repo, pr_number)
            if diff is None:
                await mark_sha_status(head_sha, "failed")
                await finalize_review(pr_id, [], status="error")
                return

            await initiate_review(repo, pr_number, status="analyzing") # Update status indicator
            diff_mapping = DiffValidator.parse_diff_mapping(diff)

            # 2. AI Analysis
            analysis = await analyze_code(diff)
            if analysis.get("status") == "failed":
                await mark_sha_status(head_sha, "failed")
                await finalize_review(pr_id, [], status="error")
                return

            # 3. Multi-Layer Validation (Mapping + Syntax)
            raw_issues = parse_and_filter_issues(analysis)

            # Layer 1: Diff Mapping validation
            mapped_issues = [i for i in raw_issues if DiffValidator.validate_issue(i, diff_mapping)]

            # Layer 2: Technical Integrity (Syntax) validation
            valid_issues = [i for i in mapped_issues if SyntaxValidator.validate_issue(i)]

            pruned_count = len(raw_issues) - len(valid_issues)
            if pruned_count > 0:
                logger.warning(f"🛡️ Multi-Layer Pruning: Removed {pruned_count} invalid issues")

            status = analysis.get("status", "success")

            if not valid_issues:
                await mark_sha_status(head_sha, "completed")
                await finalize_review(pr_id, [], status=status)
                return

            # 4. Commenting
            await finalize_review(pr_id, [], status="commenting")
            success_comments = 0
            for issue in valid_issues:
                if await post_inline_comment(owner, repo, pr_number, issue, head_sha):
                    success_comments += 1

            final_status = status if success_comments > 0 else "error"
            await mark_sha_status(head_sha, "completed" if success_comments > 0 else "failed")
            await finalize_review(pr_id, valid_issues, status=final_status)

        except Exception as e:
            logger.critical(f"🔥 [V5-OBSERVABILITY] Pipeline failure: {str(e)}", exc_info=True)
            if head_sha:
                await mark_sha_status(head_sha, "failed")
            if pr_id:
                await finalize_review(pr_id, [], status="error")

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
    if not await claim_sha_for_processing(head_sha):
        logger.info(f"🛑 [webhook] SHA {head_sha} skip: active task exists and is not stale.")
        return {"status": "ignored", "reason": "DUPLICATE_CLAIM_REJECTED"}

    background_tasks.add_task(process_webhook, payload)
    return {"status": "processing", "sha": head_sha}

@app.get("/api/stats")
async def stats(page: int = 1, authenticated: bool = Depends(get_api_key)):
    limit = 15
    offset = (page - 1) * limit
    return await get_stats(limit=limit, offset=offset)

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "enterprise-ai-reviewer", "concurrency": analysis_semaphore._value}

@app.get("/")
async def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
