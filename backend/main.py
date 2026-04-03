import logging
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables FIRST before importing singletons
load_dotenv()

# Ensure requirements specify exact functions
from services.github_service import extract_pr_data, fetch_diff, post_comment, post_inline_comment
from services.ai_service import analyze_code
from services.filter_service import parse_and_filter_issues
from utils.formatter import format_comment, format_inline_issue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
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

        # SHA Deduplication Tracking
        head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
        if not head_sha:
            return {"status": "error", "reason": "No commit SHA found in payload"}

        # if head_sha in processed_shas:
        #     print(f"[webhook] SHA {head_sha} already processed — duplicate skipped")
        #     return {"status": "duplicate skipped"}
        # processed_shas.add(head_sha)

        print("[webhook] PR detected")

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
            return {"status": "success", "issues_commented": success_count}
        else:
            return {"status": "error", "reason": "Failed to post inline comments"}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return {"error": str(e)}

    return {"status": "processed"}

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """Accepts GitHub webhooks instantly to prevent timeouts."""
    payload = await request.json()
    print("🔥 RAW PAYLOAD RECEIVED, id:", id(payload), "keys:", list(payload.keys()))
    background_tasks.add_task(process_webhook, payload)
    return {"status": "processing"}
