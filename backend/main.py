import asyncio
import logging
import os
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from services.github_service import fetch_diff, post_comment, post_inline_comment, post_status
from services.ai_service import get_ai_service
from services.diff_validator import DiffValidator
from services.syntax_validator import SyntaxValidator
from services.filter_service import parse_and_filter_issues
from stats_store import initialize_db, get_stats, record_review, finalize_review, claim_sha_for_processing, is_sha_processed, mark_sha_status, upsert_review
import stats_store

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

app = FastAPI(title="AI PR Reviewer")

# Mount static files for the dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_dashboard():
    return FileResponse("static/index.html")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "bot": "online", "database": "connected"}

# AI Analysis Semaphore to prevent Groq API overload (Max 5 concurrent)
analysis_semaphore = asyncio.BoundedSemaphore(5)

@app.on_event("startup")
async def startup():
    await initialize_db()

def compute_decision(high, medium, low, total_chunks, processed_chunks, error=False):
    """Business Logic for PR Decision Engine."""
    # CRITICAL: Any High vulnerability results in immediate BLOCK
    if high > 0:
        return "BLOCK"

    # FAIL-FAST: System error triggers BLOCK
    if error:
        return "BLOCK"
    
    # Confidence/Coverage Level
    confidence = processed_chunks / total_chunks if total_chunks > 0 else 1.0

    # HONESTY: Absolute rule - partial analysis is NEVER "SAFE" (Requirement 5)
    if processed_chunks < total_chunks:
        return "REVIEW_REQUIRED"


    # Fully analyzed logic
    if medium >= 3:
        return "REVIEW_REQUIRED"

    # SAFE: Fully processed with minimal issues
    return "SAFE"


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
    owner = repo = None
    analysis = None

    async with analysis_semaphore:
        if not await stats_store.claim_sha_for_processing(head_sha):
            logger.info(f"🛑 [process_webhook] SHA {head_sha} skip: already actively processing or completed.")
            return

        try:
            repo_full_name = payload.get("repository", {}).get("full_name", "unknown/repo")
            owner, repo = repo_full_name.split("/") if "/" in repo_full_name else ("unknown", "repo")
            # Step 0 — Mark Pending Status on GitHub
            await post_status(owner, repo, head_sha, "pending", "AI is analyzing your code...")

            logger.info(f"🚀 [Production] Starting PR #{pr_number} | SHA: {head_sha}")

            pr_id = await stats_store.upsert_review(repo, pr_number, status="processing")

            # Step 1 — Fetch Diff
            diff = payload.get("diff")
            if diff is None:
                diff = await fetch_diff(owner, repo, pr_number)
            
            if diff is None:
                raise ValueError("Failed to fetch diff from GitHub API (Network or Rate Limit error).")

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
                
                analysis = await ai_service.analyze_code(diff, progress_callback=update_progress)
                total_chunks = analysis.get("total_chunks", 1)
                processed_chunks = analysis.get("processed_chunks", 0)

                if analysis.get("status") == "failed":
                    if analysis.get("reason") == "RATE_LIMIT":
                        logger.warning(f"⚠️ [RATE LIMIT] PR #{pr_number} skipped AI due to API exhaustion.")
                        final_status = "skipped"
                        decision = "ANALYSIS_INCOMPLETE"
                    else:
                        raise ValueError(f"Stage Failed: AI Analysis — {analysis.get('reason')}")

                # Step 3 — Validate chunks
                if processed_chunks < total_chunks and final_status not in ("skipped", "error"):
                    logger.error(f"⚠️ Partial processing: {processed_chunks}/{total_chunks} chunks OK.")
                    final_status = "partial"
                
                if final_status not in ("skipped", "error"):
                    final_status = analysis.get("status", "success")
                    decision = "SAFE" # Initial assumption before issue counting
                    # Step 4 — Validation & Filtering
                    # [STRICT 3-LAYER FILTERING]
                    raw_issues = analysis.get("issues", [])
                    raw_issues = parse_and_filter_issues({"issues": raw_issues}, diff)
                    
                    diff_mapping = DiffValidator.parse_diff_mapping(diff)

                    # Step 5 — Syntax check, Deduplication & Split Logic (Requirement 7)
                    seen_issues = set()
                    for i in raw_issues:
                        # Architecture Check: Distinguish Global vs Inline issues
                        try:
                            line_num = int(i.get("line", 0))
                        except (ValueError, TypeError):
                            line_num = 0

                        i["line"] = line_num # ensure int
                        
                        # Deduplication logic: file + line + description hash
                        issue_fingerprint = f"{i.get('file')}:{line_num}:{i.get('description')}"
                        if issue_fingerprint in seen_issues:
                            continue
                        seen_issues.add(issue_fingerprint)

                        if line_num > 0:
                            # Inline issue: MUST be in the diff mapping
                            if not DiffValidator.validate_issue(i, diff_mapping):
                                continue
                        else:
                            # Global issue: line 0. Accepted without diff check.
                            pass

                        # Syntax check
                        if not SyntaxValidator.validate_issue(i):
                            i["severity"] = "low"
                            i["description"] = f"[NEEDS REVIEW: SUGGESTION SYNTAX ERR] {i.get('description', '')}"

                        valid_issues.append(i)


                    high_count = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "high")
                    med_count  = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "medium")
                    low_count  = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "low")

                    rule_based_count = analysis.get("rule_based_count", 0)
                    
                    # Apply Confidence Kill Switch from AI Service or based on counts
                    decision = analysis.get("decision_status", "SAFE")
                    if decision == "SAFE":
                        decision = compute_decision(high_count, med_count, low_count, total_chunks, processed_chunks)
                    
                    # Deterministic Override: Static scanner beats AI
                    if rule_based_count > 0:
                        logger.warning(f"🛡️ RULE OVERRIDE: {rule_based_count} static risks found. Forcing BLOCK.")
                        decision = "BLOCK"
                    
                    if decision == "SAFE" and rule_based_count > 0:
                        logger.warning("🚨 [DISAGREEMENT] AI suggested SAFE but Rule Guard found critical risks.")

                    # Architecture Check: Detect "Suspicious SAFE" (Large diff but 0 issues)
                    if processed_chunks > 0 and len(valid_issues) == 0 and len(diff) > 5000:
                        logger.warning(f"🚨 [AI EMPTY] AI suggested SAFE with 0 issues on large diff ({len(diff)} chars).")

                    # Step 6 — Split Comment Strategy
                    all_comments_posted = True
                    global_issues = [i for i in valid_issues if i.get("line") == 0]
                    inline_issues = [i for i in valid_issues if i.get("line", 0) > 0]

                    failed_inline_count = 0
                    for issue in inline_issues:
                        suggestion = DiffValidator.generate_suggestion(issue, diff_mapping)
                        success = await post_inline_comment(owner, repo, pr_number, issue, head_sha, suggestion=suggestion)
                        if not success:
                            all_comments_posted = False
                            failed_inline_count += 1

                    # Reliability Fallback / Summary Comment
                    if global_issues or failed_inline_count > 0 or decision != "SAFE" or processed_chunks < total_chunks:
                        coverage_pct = int((processed_chunks/total_chunks)*100) if total_chunks > 0 else 100
                        if processed_chunks > 0 and coverage_pct == 0: coverage_pct = 1
                        
                        summary_lines = [
                            f"### 🤖 AI Code Review Summary — Decision: **{decision}**",
                            f"**Coverage:** {coverage_pct}% of diff analyzed."
                        ]
                        
                        if coverage_pct < 10:
                            summary_lines.insert(1, "🚨 **CRITICAL: EXTREMELY LOW COVERAGE**")
                            summary_lines.insert(2, "Only a tiny fraction of this large PR was analyzed due to safety/rate limits. **Manual review is mandatory for the remaining sections.**")

                        if processed_chunks < total_chunks:
                            summary_lines.append("⚠️ **Analysis Incomplete**")
                            
                            file_cov = analysis.get("file_coverage", {})
                            if file_cov:
                                summary_lines.append("\n#### 📂 File Coverage Status:")
                                for f, status in list(file_cov.items())[:10]: # Cap at 10 for readability
                                    icon = "✅" if status == "FULLY_ANALYZED" else "⚠️" if status == "PARTIAL" else "🚫"
                                    summary_lines.append(f"- {icon} `{f}`: {status.replace('_', ' ')}")
                                if len(file_cov) > 10:
                                    summary_lines.append(f"- ... and {len(file_cov)-10} more files.")
                            
                            summary_lines.append("\n**Manual review is required for the incomplete sections.**")
                        else:
                            summary_lines.append(f"**Status:** {high_count} High, {med_count} Medium, {low_count} Low severity issues identified.")
                            summary_lines.append("")

                        if global_issues:
                            summary_lines.append("#### 🌐 General / Architecture Feedback")
                            for g in global_issues:
                                summary_lines.append(f"- **[{g['severity']}] {g['title']}**: {g['description']}")
                            summary_lines.append("")

                        if failed_inline_count > 0:
                            summary_lines.append(f"⚠️ **Note:** {failed_inline_count} inline suggestions could not be rendered (likely mapping errors). Check the dashboard for full details.")

                        summary_body = "\n".join(summary_lines)
                        try:
                            posted = await post_comment(owner, repo, pr_number, summary_body)
                            if not posted:
                                raise ValueError("GitHub rejected the summary comment.")
                        except Exception as e:
                            logger.error(f"CRITICAL: Final fallback (summary comment) failed: {str(e)}")
                            # If we reached here, both inline and summary failed -> trigger Fail-Safe BLOCK
                            raise ValueError("Critical action failure: Both inline and summary comments failed.") from e

                    logger.info("✅ Pipeline reached finalization point.")
                    if final_status not in ("partial", "skipped"):
                        final_status = "success"

        except Exception as e:
            logger.critical(f"🔥 Fail-Safe Triggered: {str(e)}", exc_info=True)
            final_status = "error"
            decision = "BLOCK"

        finally:
            if pr_id is not None:
                high_count = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "high")
                med_count  = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "medium")
                low_count  = sum(1 for i in valid_issues if str(i.get("severity", "")).lower() == "low")
                await stats_store.finalize_review(
                    pr_id, valid_issues,
                    status=final_status,
                    decision_status=decision,
                    high=high_count,
                    medium=med_count,
                    low=low_count,
                    total_chunks=total_chunks,
                    processed_chunks=processed_chunks
                )

            if head_sha:
                await stats_store.mark_sha_status(head_sha, "completed" if final_status == "success" else "failed")
                if owner and repo:
                    status_state = "success" if decision == "SAFE" else "failure"
                    if final_status == "error": status_state = "error"
                    status_desc = f"Review: {decision}. Found {len(valid_issues)} issues."
                    await post_status(owner, repo, head_sha, status_state, status_desc)

            logger.info(f"🏁 [Webhook Finalized] PR={pr_number} Status={final_status} Decision={decision} Issues={len(valid_issues)}")

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": "UNSUPPORTED_ACTION"}
    head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
    if not head_sha: return {"status": "error", "reason": "MISSING_SHA"}
    if await stats_store.is_sha_processed(head_sha):
        return {"status": "ignored", "reason": "ALREADY_PROCESSED"}
    background_tasks.add_task(process_webhook, payload)
    return {"status": "processing", "sha": head_sha}

@app.get("/api/stats")
async def api_stats():
    return await get_stats()
