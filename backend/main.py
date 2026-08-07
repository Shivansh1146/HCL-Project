import asyncio
import json
import logging
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()  # Must be first — sets env vars before any other import reads them

import stats_store
from auth.store import initialize_auth_db, is_repo_whitelisted
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from routers.analytics_router import router as analytics_router
from routers.app_router import app_router as public_app_router
from routers.app_router import repo_alias_router
from routers.app_router import router as app_router
from routers.auth_router import router as auth_router
from routers.pr_router import router as pr_router
from routers.webhook_router import router as webhook_router
from services.ai_service import get_ai_service
from services.diff_validator import DiffValidator
from services.filter_service import parse_and_filter_issues
from services.github_service import (
    fetch_diff,
    post_comment,
    post_inline_comment,
    post_status,
)
from services.syntax_validator import SyntaxValidator
from services.validator import AntiHallucinationValidator
from stats_store import (
    claim_sha_for_processing,
    finalize_review,
    get_stats,
    initialize_db,
    is_sha_processed,
    mark_sha_status,
    upsert_review,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

app = FastAPI(title="AI PR Reviewer", version="1.0.0")

# ---------------------------------------------------------------------------
# Security Middleware
# ---------------------------------------------------------------------------
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
_is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"

if _is_prod and _allowed_origins_env:
    _cors_origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
else:
    # Development: allow localhost on common ports
    _cors_origins = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=(
        ["localhost", "127.0.0.1", "*.hcl.com", "*"] if not _is_prod else ["*.hcl.com"]
    ),
)

# Include Routers
app.include_router(auth_router)
app.include_router(app_router)
app.include_router(public_app_router)
app.include_router(repo_alias_router)
app.include_router(pr_router)
app.include_router(analytics_router)
app.include_router(webhook_router)

# Mount static files for the dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_dashboard():
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "bot": "online", "database": "connected"}


@app.get("/api/health/ai")
async def ai_health_check():
    """Health check endpoint for AI service configuration and connectivity."""
    try:
        ai_service = get_ai_service()
        health_status = await ai_service.health_check()
        return health_status
    except Exception as e:
        logger.error(f"AI health check failed: {str(e)}")
        return {
            "groq_configured": False,
            "groq_reachable": False,
            "model": "unknown",
            "status": "error",
            "reason": str(e)
        }


@app.get("/api/debug/pr/{owner}/{repo}/{pr_number}")
async def debug_pr(owner: str, repo: str, pr_number: int):
    """Debug endpoint to trace PR processing in production."""
    from auth.store import is_repo_whitelisted, get_pull_request
    from stats_store import is_sha_processed
    
    repo_full_name = f"{owner}/{repo}"
    
    # Check repository whitelist
    whitelist_result = await is_repo_whitelisted(repo_full_name)
    
    # Check if PR exists in database
    try:
        pr_record = await get_pull_request(pr_number, repo_full_name)
        pr_exists = pr_record is not None
        pr_data = pr_record if pr_exists else None
    except Exception as e:
        pr_exists = False
        pr_data = {"error": str(e)}
    
    # Check database for webhook deliveries
    async with get_db() as db:
        # Check webhook deliveries
        async with db.execute(
            "SELECT * FROM webhook_deliveries ORDER BY processed_at DESC LIMIT 10"
        ) as cursor:
            webhook_rows = await cursor.fetchall()
            recent_webhooks = [
                {
                    "delivery_id": row["delivery_id"],
                    "event_type": row["event_type"],
                    "action": row["action"],
                    "status": row["status"],
                    "processed_at": row["processed_at"]
                }
                for row in webhook_rows
            ]
        
        # Check selected repos
        async with db.execute(
            "SELECT COUNT(*) as cnt FROM selected_repos WHERE enabled = 1"
        ) as cursor:
            row = await cursor.fetchone()
            total_selected = row["cnt"] if row else 0
        
        async with db.execute(
            "SELECT repo_full_name, enabled FROM selected_repos WHERE enabled = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            selected_repos = [
                {"repo_full_name": row["repo_full_name"], "enabled": row["enabled"]}
                for row in rows
            ]
    

    return {
        "repository": repo_full_name,
        "pr_number": pr_number,
        "whitelist_result": whitelist_result,
        "total_selected_repos": total_selected,
        "selected_repos": selected_repos,
        "pr_exists_in_db": pr_exists,
        "pr_data": pr_data,
        "recent_webhooks": recent_webhooks
    }


@app.get("/api/debug/review/{owner}/{repo}/{pr_number}")
async def debug_review(owner: str, repo: str, pr_number: int):
    """Debug endpoint to check AI review status for a PR."""
    from auth.store import get_pull_request
    from db_engine import get_db
    
    repo_full_name = f"{owner}/{repo}"
    
    try:
        # First check what columns exist in pull_requests table
        async with get_db() as db:
            async with db.execute("PRAGMA table_info(pull_requests);") as cursor:
                existing_cols = {row["name"] for row in await cursor.fetchall()}
        
        # Get PR record
        pr_record = await get_pull_request(pr_number, repo_full_name)
        if not pr_record:
            return {"error": "PR not found in database"}
        
        # Build response with only existing columns
        response = {
            "repository": repo_full_name,
            "pr_number": pr_number,
            "existing_columns": list(existing_cols),
        }
        
        # Add review columns if they exist
        review_cols = {
            "review_status", "decision", "review_summary", "issues_count",
            "high_count", "medium_count", "low_count", "coverage_percentage",
            "reviewed_at", "review_published", "review_posted", "github_review_id"
        }
        
        for col in review_cols:
            if col in existing_cols:
                response[col] = pr_record.get(col)
            else:
                response[col] = "COLUMN_NOT_EXIST"
        
        return response
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# AI Analysis Semaphore to prevent Groq API overload (Max 5 concurrent)
analysis_semaphore = asyncio.BoundedSemaphore(5)

from db_engine import (  # noqa: E402 (imported after load_dotenv intentionally)
    close_db_engine,
    init_db_engine,
    get_db,
)


@app.on_event("startup")
async def startup():
    await init_db_engine()
    await initialize_db()
    await initialize_auth_db()
    
    # Validate AI service configuration
    ai_service = get_ai_service()
    if ai_service.is_configured():
        logger.info("✓ GROQ_API_KEY loaded")
    else:
        logger.warning("✗ GROQ_API_KEY missing - AI review functionality disabled")


@app.on_event("shutdown")
async def shutdown():
    await close_db_engine()


def compute_decision(high, medium, low, total_chunks, processed_chunks, error=False):
    """Business Logic for PR Decision Engine."""
    # CRITICAL: Any High vulnerability results in immediate BLOCK
    if high > 0:
        return "BLOCK"

    # FAIL-FAST: System error triggers BLOCK
    if error:
        return "BLOCK"

    # HONESTY: Absolute rule - partial analysis is NEVER "SAFE" (Requirement 5)
    if processed_chunks < total_chunks:
        return "REVIEW_REQUIRED"

    # Fully analyzed logic
    if medium >= 3:
        return "REVIEW_REQUIRED"

    # PERFECT: Fully processed with ZERO issues
    if high == 0 and medium == 0 and low == 0:
        return "PERFECT"

    # SAFE: Fully processed with minimal issues
    return "SAFE"


def generate_decision_explanation(
    high, medium, low, total_chunks, processed_chunks, rule_based_count, error=False
):
    """
    Computes a detailed explanation for the PR decision based on real pipeline metrics.
    STRICT: Reflects logic from compute_decision() and rule overrides.
    """
    reasons = []

    # Use existing decision logic
    decision = compute_decision(
        high, medium, low, total_chunks, processed_chunks, error=error
    )

    # Rule-based override (matches main pipeline logic)
    if rule_based_count > 0:
        decision = "BLOCK"
        reasons.append(
            f"Policy Violation: {rule_based_count} security risks identified by static rule engine."
        )

    if error:
        reasons.append("System error occurred during analysis (Fail-Safe triggered).")
    elif high > 0:
        reasons.append(
            f"Critical Risk: {high} high-severity vulnerability/vulnerabilities detected."
        )
    elif processed_chunks < total_chunks:
        coverage_pct = (
            round((processed_chunks / total_chunks * 100), 1) if total_chunks > 0 else 0
        )
        reasons.append(
            f"Incomplete Analysis: Only {coverage_pct}% of the code was analyzed due to size/rate limits."
        )
        reasons.append("Manual review is mandatory for unverified sections.")
    elif medium >= 3:
        reasons.append(
            f"Threshold Reached: {medium} medium-severity issues found (Limit: 3)."
        )
    elif high == 0 and medium == 0 and low == 0:
        reasons.append("Clean PR: Fully processed with zero identified issues.")
    else:
        reasons.append(
            f"Verified: {low} low-severity improvements suggested, but no critical risks found."
        )

    return {
        "decision": decision,
        "reasons": reasons,
        "metrics": {
            "high": high,
            "medium": medium,
            "low": low,
            "coverage": (
                round((processed_chunks / total_chunks * 100), 1)
                if total_chunks > 0
                else 100
            ),
            "rule_based": rule_based_count,
        },
    }


async def process_webhook(payload: dict):
    """Production-grade fail-safe pipeline with guaranteed finalization."""
    head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
    repo_full_name = payload.get("repository", {}).get("full_name", "unknown/repo")
    pr_number = payload.get("pull_request", {}).get("number")

    # Internal state for finalization recovery
    pr_id = None
    final_status = "success"
    decision = "BLOCK"
    valid_issues = []
    total_chunks = 0
    processed_chunks = 0
    rule_based_count = 0
    owner = repo = None

    analysis = None

    async with analysis_semaphore:
        if not await stats_store.claim_sha_for_processing(head_sha):
            logger.info(
                f"🛑 [process_webhook] SHA {head_sha} skip: already actively processing or completed."
            )
            return

        try:
            repo_full_name = payload.get("repository", {}).get(
                "full_name", "unknown/repo"
            )
            owner, repo = (
                repo_full_name.split("/")
                if "/" in repo_full_name
                else ("unknown", "repo")
            )
            # Step 0 — Mark Pending Status on GitHub
            await post_status(
                owner, repo, head_sha, "pending", "AI is analyzing your code..."
            )

            logger.info(f"🚀 [Production] Starting PR #{pr_number} | SHA: {head_sha}")

            pr_id = await stats_store.upsert_review(
                repo, pr_number, status="processing"
            )

            # Step 1 — Fetch Diff
            diff = payload.get("diff")
            if diff is None:
                diff = await fetch_diff(owner, repo, pr_number)

            if diff is None:
                raise ValueError(
                    "Failed to fetch diff from GitHub API (Network or Rate Limit error)."
                )

            if not diff:
                total_chunks = 0
                processed_chunks = 0
                final_status = "success"
                decision = compute_decision(0, 0, 0, 0, 0, error=False)
                logger.info(f"⏭️ PR #{pr_number} has no code changes — marking SAFE.")
            else:
                # Step 2 — AI Analysis
                ai_service = get_ai_service()

                async def update_progress(p, t):
                    await stats_store.update_review_progress(pr_id, p, t)

                analysis = await ai_service.analyze_code(
                    diff, progress_callback=update_progress
                )
                total_chunks = analysis.get("total_chunks", 1)
                processed_chunks = analysis.get("processed_chunks", 0)

                if analysis.get("status") == "failed":
                    if analysis.get("reason") == "RATE_LIMIT":
                        logger.warning(
                            f"⚠️ [RATE LIMIT] PR #{pr_number} skipped AI due to API exhaustion."
                        )
                        final_status = "skipped"
                        decision = "ANALYSIS_INCOMPLETE"
                    else:
                        raise ValueError(
                            f"Stage Failed: AI Analysis — {analysis.get('reason')}"
                        )

                # Step 3 — Validate chunks
                if processed_chunks < total_chunks and final_status not in (
                    "skipped",
                    "error",
                ):
                    logger.error(
                        f"⚠️ Partial processing: {processed_chunks}/{total_chunks} chunks OK."
                    )
                    final_status = "partial"

                if final_status not in ("skipped", "error"):
                    final_status = analysis.get("status", "success")
                    decision = "SAFE"  # Initial assumption before issue counting
                    # Step 4 — Validation & Filtering
                    # [STRICT 3-LAYER FILTERING]
                    raw_issues = analysis.get("issues", [])
                    raw_issues = parse_and_filter_issues({"issues": raw_issues}, diff)

                    diff_mapping = DiffValidator.parse_diff_mapping(diff)

                    # Step 5 — Syntax check, Deduplication & Split Logic (Requirement 7)
                    # Rule 2: Stable Deduplication (file:line:title)
                    seen_fingerprints = set()
                    final_valid_issues = []

                    for i in raw_issues:
                        try:
                            line_num = int(i.get("line", 0))
                        except (ValueError, TypeError):
                            line_num = 0
                        i["line"] = line_num

                        # Fingerprint check using title (Stability Rule 2)
                        issue_fingerprint = (
                            f"{i.get('file')}:{line_num}:{i.get('title')}"
                        )
                        if issue_fingerprint in seen_fingerprints:
                            continue
                        seen_fingerprints.add(issue_fingerprint)

                        # 🔍 Auto-Correct line mapping
                        AntiHallucinationValidator.auto_correct_line_mapping(
                            i, diff_mapping.get(i.get("file", ""), {})
                        )

                        if line_num > 0:
                            if not DiffValidator.validate_issue(i, diff_mapping):
                                continue

                            # 🛡️ CONTENT GUARD: Never replace comments or keywords with logic
                            file_key = i.get("file", "")
                            if (
                                file_key in diff_mapping
                                and line_num in diff_mapping[file_key]
                            ):
                                old_content, _ = diff_mapping[file_key][line_num]
                                old_clean = old_content.strip()
                                if old_clean.startswith("#") or old_clean in [
                                    "else:",
                                    "elif:",
                                    "while:",
                                    "if",
                                ]:
                                    logger.info(
                                        f"🛡️ [CONTENT GUARD] Blocked attempt to replace '{old_clean}' with logic."
                                    )
                                    continue

                        # Syntax check (🛡️ HARDENED: Drop syntax errors completely)
                        if not SyntaxValidator.validate_issue(i):
                            logger.info(
                                f"🚫 [SYNTAX GUARD] Dropped malformed suggestion for {file_key}:{line_num}"
                            )
                            continue

                        final_valid_issues.append(i)

                    # Rule 3: Stability Stop (MOST IMPORTANT)
                    # Get existing issues from DB to see if we've already reported exactly these
                    existing_issues = await stats_store.get_issues_for_pr(pr_number)
                    existing_fingerprints = {
                        f"{iss['file']}:{iss['line']}:{iss['title']}"
                        for iss in existing_issues
                    }
                    new_fingerprints = {
                        f"{iss['file']}:{iss['line']}:{iss['title']}"
                        for iss in final_valid_issues
                    }

                    if (
                        existing_fingerprints == new_fingerprints
                        and len(new_fingerprints) > 0
                    ):
                        logger.info(
                            f"⚖️ [Stability Stop] No new issues for PR #{pr_number}. Stopping redundant analysis."
                        )
                        valid_issues = []  # Clear to prevent re-posting
                    else:
                        valid_issues = final_valid_issues

                    high_count = sum(
                        1
                        for i in valid_issues
                        if str(i.get("severity", "")).lower() == "high"
                    )
                    med_count = sum(
                        1
                        for i in valid_issues
                        if str(i.get("severity", "")).lower() == "medium"
                    )
                    low_count = sum(
                        1
                        for i in valid_issues
                        if str(i.get("severity", "")).lower() == "low"
                    )
                    rule_based_count = analysis.get("rule_based_count", 0)

                    # Generate Real Explainability Data
                    explanation_data = generate_decision_explanation(
                        high_count,
                        med_count,
                        low_count,
                        total_chunks,
                        processed_chunks,
                        rule_based_count,
                        error=False,
                    )
                    decision = explanation_data["decision"]

                    # Deterministic Override: Static scanner beats AI
                    if rule_based_count > 0:
                        decision = "BLOCK"

                    if decision == "SAFE" and rule_based_count > 0:
                        logger.warning(
                            "🚨 [DISAGREEMENT] AI suggested SAFE but Rule Guard found critical risks."
                        )

                    # Architecture Check: Detect "Suspicious SAFE" (Large diff but 0 issues)
                    if (
                        processed_chunks > 0
                        and len(valid_issues) == 0
                        and len(diff) > 5000
                    ):
                        logger.warning(
                            f"🚨 [AI EMPTY] AI suggested SAFE with 0 issues on large diff ({len(diff)} chars)."
                        )

                    # Step 6 — Split Comment Strategy
                    global_issues = [i for i in valid_issues if i.get("line") == 0]
                    inline_issues = [i for i in valid_issues if i.get("line", 0) > 0]

                    failed_inline_count = 0
                    for issue in inline_issues:
                        suggestion = DiffValidator.generate_suggestion(
                            issue, diff_mapping
                        )
                        success = await post_inline_comment(
                            owner,
                            repo,
                            pr_number,
                            issue,
                            head_sha,
                            suggestion=suggestion,
                        )
                        if not success:
                            failed_inline_count += 1

                    # Reliability Fallback / Summary Comment
                    if (
                        global_issues
                        or failed_inline_count > 0
                        or decision != "SAFE"
                        or processed_chunks < total_chunks
                    ):
                        coverage_pct = (
                            int((processed_chunks / total_chunks) * 100)
                            if total_chunks > 0
                            else 100
                        )
                        if processed_chunks > 0 and coverage_pct == 0:
                            coverage_pct = 1

                        summary_lines = [
                            f"### 🤖 AI Code Review Summary — Decision: **{decision}**",
                            f"**Coverage:** {coverage_pct}% of diff analyzed.",
                        ]

                        # Add real explanation reasons to the GitHub comment
                        if "explanation_data" in locals():
                            summary_lines.append("\n**Decision Rationale:**")
                            for r in explanation_data.get("reasons", []):
                                summary_lines.append(f"- {r}")

                        if coverage_pct < 10:
                            summary_lines.insert(
                                1, "🚨 **CRITICAL: EXTREMELY LOW COVERAGE**"
                            )
                            summary_lines.insert(
                                2,
                                "Only a tiny fraction of this large PR was analyzed due to safety/rate limits. **Manual review is mandatory for the remaining sections.**",
                            )

                        if processed_chunks < total_chunks:
                            summary_lines.append("⚠️ **Analysis Incomplete**")

                            file_cov = analysis.get("file_coverage", {})
                            if file_cov:
                                summary_lines.append("\n#### 📂 File Coverage Status:")
                                for f, status in list(file_cov.items())[
                                    :10
                                ]:  # Cap at 10 for readability
                                    icon = (
                                        "✅"
                                        if status == "FULLY_ANALYZED"
                                        else "⚠️" if status == "PARTIAL" else "🚫"
                                    )
                                    summary_lines.append(
                                        f"- {icon} `{f}`: {status.replace('_', ' ')}"
                                    )
                                if len(file_cov) > 10:
                                    summary_lines.append(
                                        f"- ... and {len(file_cov)-10} more files."
                                    )

                            summary_lines.append(
                                "\n**Manual review is required for the incomplete sections.**"
                            )
                        else:
                            summary_lines.append(
                                f"**Status:** {high_count} High, {med_count} Medium, {low_count} Low severity issues identified."
                            )
                            summary_lines.append("")

                        if global_issues:
                            summary_lines.append(
                                "#### 🌐 General / Architecture Feedback"
                            )
                            for g in global_issues:
                                summary_lines.append(
                                    f"- **[{g['severity']}] {g['title']}**: {g['description']}"
                                )
                            summary_lines.append("")

                        if failed_inline_count > 0:
                            summary_lines.append(
                                f"⚠️ **Note:** {failed_inline_count} inline suggestions could not be rendered (likely mapping errors). Check the dashboard for full details."
                            )

                        summary_body = "\n".join(summary_lines)
                        try:
                            posted = await post_comment(
                                owner, repo, pr_number, summary_body
                            )
                            if not posted:
                                raise ValueError("GitHub rejected the summary comment.")
                        except Exception as e:
                            logger.error(
                                f"CRITICAL: Final fallback (summary comment) failed: {str(e)}"
                            )
                            # If we reached here, both inline and summary failed -> trigger Fail-Safe BLOCK
                            raise ValueError(
                                "Critical action failure: Both inline and summary comments failed."
                            ) from e

                    logger.info("✅ Pipeline reached finalization point.")
                    if final_status not in ("partial", "skipped"):
                        final_status = "success"

        except Exception as e:
            logger.critical(f"🔥 Fail-Safe Triggered: {str(e)}", exc_info=True)
            final_status = "error"
            decision = "BLOCK"

        finally:
            if pr_id is not None:
                # Re-calculate counts if valid_issues changed or to ensure consistency
                high_count = sum(
                    1
                    for i in valid_issues
                    if str(i.get("severity", "")).lower() == "high"
                )
                med_count = sum(
                    1
                    for i in valid_issues
                    if str(i.get("severity", "")).lower() == "medium"
                )
                low_count = sum(
                    1
                    for i in valid_issues
                    if str(i.get("severity", "")).lower() == "low"
                )

                # Final pass for explainability (catches errors in finally block)
                explanation_data = generate_decision_explanation(
                    high_count,
                    med_count,
                    low_count,
                    total_chunks,
                    processed_chunks,
                    rule_based_count,
                    error=(final_status == "error"),
                )

                await stats_store.finalize_review(
                    pr_id,
                    valid_issues,
                    status=final_status,
                    decision_status=explanation_data["decision"],
                    high=high_count,
                    medium=med_count,
                    low=low_count,
                    total_chunks=total_chunks,
                    processed_chunks=processed_chunks,
                    rule_based_count=rule_based_count,
                    decision_explanation=json.dumps(explanation_data),
                )

            if head_sha:
                await stats_store.mark_sha_status(
                    head_sha, "completed" if final_status == "success" else "failed"
                )
                if owner and repo:
                    status_state = (
                        "success" if decision in ("SAFE", "PERFECT") else "failure"
                    )
                    if final_status == "error":
                        status_state = "error"
                    status_desc = (
                        f"Review: {decision}. Found {len(valid_issues)} issues."
                    )
                    await post_status(owner, repo, head_sha, status_state, status_desc)

            logger.info(
                f"🏁 [Webhook Finalized] PR={pr_number} Status={final_status} Decision={decision} Issues={len(valid_issues)}"
            )


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": "UNSUPPORTED_ACTION"}

    # Requirement #7: Automatically verify webhook events belong to installed/selected repositories
    repo_full_name = payload.get("repository", {}).get("full_name", "")
    if repo_full_name and not await is_repo_whitelisted(repo_full_name):
        logger.info(
            f"🚫 Webhook ignored: Repository '{repo_full_name}' is not in selected repositories list."
        )
        return {"status": "ignored", "reason": "REPOSITORY_NOT_SELECTED"}

    head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
    if not head_sha:
        return {"status": "error", "reason": "MISSING_SHA"}
    if await stats_store.is_sha_processed(head_sha):
        return {"status": "ignored", "reason": "ALREADY_PROCESSED"}
    background_tasks.add_task(process_webhook, payload)
    return {"status": "processing", "sha": head_sha}


@app.post("/api/admin/clean")
async def admin_clean_db(request: Request):
    """Admin endpoint: Clean all DB records EXCEPT PR #777."""
    body = (
        await request.json()
        if request.headers.get("content-type") == "application/json"
        else {}
    )
    keep_pr = body.get("keep_pr", 777)

    async with stats_store.get_db() as db:
        # Find row ids for the PR to keep
        async with db.execute(
            "SELECT id FROM prs WHERE pr_number = ?", (keep_pr,)
        ) as cursor:
            keep_rows = await cursor.fetchall()
        keep_ids = [row[0] for row in keep_rows]

        if keep_ids:
            placeholders = ",".join("?" * len(keep_ids))
            del_issues = await db.execute(
                f"DELETE FROM issues WHERE pr_id NOT IN ({placeholders})", keep_ids
            )
            del_prs = await db.execute(
                f"DELETE FROM prs WHERE id NOT IN ({placeholders})", keep_ids
            )
        else:
            del_issues = await db.execute("DELETE FROM issues")
            del_prs = await db.execute("DELETE FROM prs")

        await db.execute("DELETE FROM processed_shas")
        await db.commit()

    logger.info(f"[ADMIN] DB cleaned. Kept PR #{keep_pr} (ids={keep_ids})")
    return {"status": "cleaned", "kept_pr": keep_pr, "kept_ids": keep_ids}


@app.get("/api/stats")
async def api_stats():
    return await get_stats()
