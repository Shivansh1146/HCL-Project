import logging
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

# Load environment variables FIRST before importing singletons
load_dotenv()

# Ensure requirements specify exact functions
from services.github_service import extract_pr_data, fetch_diff, post_comment, post_inline_comment
from services.ai_service import analyze_code
from services.filter_service import parse_and_filter_issues
from utils.formatter import format_comment, format_inline_issue

from stats_store import record_review, get_stats, initialize_db
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Initialize database on startup
initialize_db()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler("backend_log.txt"),
        logging.StreamHandler()
    ]
)

app = FastAPI(
    title="Project API",
    description="Backend API for the full-stack project.",
    version="1.0.0"
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path resolution for static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/api/stats")
async def stats():
    return get_stats()

@app.get("/")
async def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# In-memory deduplication set for processed commit SHAs
processed_shas = set()

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify backend status."""
    return {"status": "healthy"}

@app.get("/api/info")
async def get_info():
    """Returns some generic info to display on the frontend."""
    return {
        "message": "Welcome to the API!",
        "services": ["github", "ai", "filter"]
    }

def process_webhook(payload: dict):
    """Heavy background logic execution."""
    print("🚀 BACKGROUND TASK STARTED")
    print("📦 KEYS:", list(payload.keys()))
    try:
        # Stage 1
        if "pull_request" not in payload:
            print("❌ NO PR FOUND → IGNORING")
            return
        print("✅ PR DETECTED → CONTINUING")

        # Stage 2
        action = payload.get("action")
        if action not in ["opened", "synchronize"]:
            print(f"[webhook] Skipping action: {action}")
            return {"status": "ignored", "reason": f"Skipping action: {action}"}

        # Stage 3
        owner, repo, pr_number = extract_pr_data(payload)
        head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")

        print(f"[webhook] PR detected: #{pr_number} by {owner} at {head_sha}")

        # Stage 4
        # We pass the full payload to the updated fetch_diff
        diff = fetch_diff(owner, repo, pr_number)
        if not diff:
            print("📦 DIFF LENGTH: 0")
            print("[webhook] Empty diff — skipping")
            return {"status": "no changes"}
        print("📦 DIFF LENGTH:", len(diff))

        # Stage 5
        analysis_result = analyze_code(diff)
        print("🧠 AI RESPONSE:", analysis_result)

        # Stage 6
        issues = parse_and_filter_issues(analysis_result)
        print("🧹 FILTERED ISSUES:", issues)

        # Stage 7
        if not issues:
            print("[webhook] No issues found — skipping comment")
            return {"status": "clean"}

        # Stage 8 & 9 & 10
        success_count = 0
        for issue in issues:
            formatted_body = format_inline_issue(issue)
            issue["formatted_body"] = formatted_body
            print("📤 POSTING COMMENT...")
            if post_inline_comment(owner, repo, pr_number, issue, head_sha):
                print("✅ COMMENT POSTED")
                success_count += 1
            else:
                print("[post_inline_comment] error")

        if success_count > 0:
            print("[webhook] successfully posted inline comments")
            record_review(repo, pr_number, issues)
            return {"status": "success", "issues_commented": success_count}
        else:
            record_review(repo, pr_number, issues)
            return {"status": "error", "reason": "Failed to post inline comments"}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return {"error": str(e)}

    return {"status": "processed"}

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """Accepts GitHub webhooks instantly to prevent timeouts."""
    payload = await request.json()

    # Synchronous de-duplication to prevent race conditions
    head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
    if head_sha:
        if head_sha in processed_shas:
            print(f"🛑 [webhook] SHA {head_sha} already being processed/done. Skipping.")
            return {"status": "duplicate_skipped", "sha": head_sha}
        processed_shas.add(head_sha)
        print(f"🎯 [webhook] Registered SHA {head_sha} for processing.")

    print("🔥 RAW PAYLOAD RECEIVED, id:", id(payload), "keys:", list(payload.keys()))
    background_tasks.add_task(process_webhook, payload)
    return {"status": "processing"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
