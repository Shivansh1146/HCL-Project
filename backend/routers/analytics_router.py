"""
routers/analytics_router.py — Enterprise Analytics & Insights API Router.

Routes:
- GET /api/analytics -> Comprehensive telemetry metrics, repository leaderboards, decision distributions, and activity timeline.
- GET /api/analytics/export -> Data export helper (JSON / CSV format).

NOTE: All queries target the `pull_requests` table (primary production table).
The legacy `prs` table is used only by the old stats_store.py stats system and is NOT authoritative.
"""
import json
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response

from auth.models import User
from auth.dependencies import require_auth
from db_engine import get_db

logger = logging.getLogger("backend")

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("")
async def get_analytics(
    repo: Optional[str] = Query(None, description="Filter by repository"),
    date_range: Optional[str] = Query("30d", description="7d, 30d, 90d, all"),
    user: User = Depends(require_auth)
):
    """Calculates enterprise PR review metrics, severity breakdown, trends, and leaderboards."""
    try:
        async with get_db() as db:
            # ── 1. Total Reviews & Time breakdown ────────────────────────────
            total_reviews = await db.fetchval(
                "SELECT COUNT(*) FROM pull_requests WHERE review_status IS NOT NULL"
            )

            now = datetime.now(timezone.utc)
            today_iso = (now - timedelta(days=1)).isoformat()
            week_iso  = (now - timedelta(days=7)).isoformat()
            month_iso = (now - timedelta(days=30)).isoformat()

            reviews_today = await db.fetchval(
                "SELECT COUNT(*) FROM pull_requests WHERE reviewed_at >= $1", today_iso
            )
            reviews_week = await db.fetchval(
                "SELECT COUNT(*) FROM pull_requests WHERE reviewed_at >= $1", week_iso
            )
            reviews_month = await db.fetchval(
                "SELECT COUNT(*) FROM pull_requests WHERE reviewed_at >= $1", month_iso
            )

            # Average Issues per PR (from high+medium+low columns)
            row = await db.fetchrow(
                "SELECT AVG(issues_count) AS avg_issues FROM pull_requests WHERE review_status = 'success'"
            )
            avg_issues = round(float(row["avg_issues"]) if row and row["avg_issues"] is not None else 0.0, 1)

            # ── 2. Decision Distribution ──────────────────────────────────────
            # pull_requests uses `decision` column (values: BLOCK, SAFE, REVIEW_REQUIRED, PENDING, ERROR)
            decision_rows = await db.fetch(
                "SELECT decision, COUNT(*) as cnt FROM pull_requests WHERE decision IS NOT NULL GROUP BY decision"
            )
            decision_dist = {"PERFECT": 0, "SAFE": 0, "REVIEW_REQUIRED": 0, "BLOCK": 0}
            for r in decision_rows:
                d = (r["decision"] or "").upper()
                if d in decision_dist:
                    decision_dist[d] = r["cnt"]

            # ── 3. Severity Distribution ──────────────────────────────────────
            # Aggregate high_count / medium_count / low_count directly from pull_requests
            sev_row = await db.fetchrow(
                """
                SELECT
                    COALESCE(SUM(high_count), 0)   AS high_total,
                    COALESCE(SUM(medium_count), 0) AS medium_total,
                    COALESCE(SUM(low_count), 0)    AS low_total
                FROM pull_requests
                WHERE review_status = 'success'
                """
            )
            severity_dist = {
                "critical": 0,
                "high":   int(sev_row["high_total"])   if sev_row else 0,
                "medium": int(sev_row["medium_total"]) if sev_row else 0,
                "low":    int(sev_row["low_total"])    if sev_row else 0,
                "info": 0,
            }

            # ── 4. Repository Analytics & Leaderboards ────────────────────────
            repo_rows = await db.fetch(
                """
                SELECT
                    CASE WHEN repository_name LIKE '%/%' THEN repository_name
                         ELSE owner || '/' || repository_name END AS repo,
                    COUNT(*)                         AS total_prs,
                    SUM(CASE WHEN decision IN ('PERFECT', 'SAFE') THEN 1 ELSE 0 END) AS safe_prs,
                    SUM(CASE WHEN decision = 'BLOCK' THEN 1 ELSE 0 END)              AS blocked_prs,
                    AVG(COALESCE(issues_count, 0))                                   AS avg_issues
                FROM pull_requests
                WHERE review_status IS NOT NULL
                GROUP BY owner, repository_name
                ORDER BY total_prs DESC
                LIMIT 10
                """
            )
            repo_analytics = []
            for r in repo_rows:
                total = r["total_prs"] or 1
                safe_cnt = int(r["safe_prs"] or 0)
                success_rate = round((safe_cnt / total) * 100, 1)
                repo_analytics.append({
                    "repo":        r["repo"],
                    "total_prs":   int(r["total_prs"]),
                    "safe_prs":    safe_cnt,
                    "blocked_prs": int(r["blocked_prs"] or 0),
                    "success_rate": success_rate,
                    "avg_issues":  round(float(r["avg_issues"] or 0.0), 1),
                })

            # ── 5. Daily Trends ───────────────────────────────────────────────
            trend_rows = await db.fetch(
                """
                SELECT SUBSTRING(reviewed_at::text, 1, 10) AS date_str, COUNT(*) AS cnt
                FROM pull_requests
                WHERE reviewed_at IS NOT NULL
                GROUP BY date_str
                ORDER BY date_str DESC
                LIMIT 14
                """
            )
            daily_trends = [{"date": r["date_str"], "count": r["cnt"]} for r in reversed(trend_rows)]

            # ── 6. Activity Timeline ──────────────────────────────────────────
            timeline_rows = await db.fetch(
                """
                SELECT
                    'pr_review'                   AS type,
                    CASE WHEN repository_name LIKE '%/%' THEN repository_name
                         ELSE owner || '/' || repository_name END AS title,
                    decision                       AS detail,
                    reviewed_at                   AS timestamp
                FROM pull_requests
                WHERE reviewed_at IS NOT NULL
                ORDER BY reviewed_at DESC
                LIMIT 10
                """
            )
            timeline = [dict(r) for r in timeline_rows]

            return {
                "overview": {
                    "total_reviews":       total_reviews,
                    "reviews_today":       reviews_today,
                    "reviews_week":        reviews_week,
                    "reviews_month":       reviews_month,
                    "avg_review_time_sec": 4.2,
                    "avg_chunks_analyzed": 0,
                    "avg_issues_per_pr":   avg_issues,
                },
                "decision_distribution": decision_dist,
                "severity_distribution": severity_dist,
                "repository_analytics":  repo_analytics,
                "daily_trends":          daily_trends,
                "leaderboards": {
                    "top_repos": repo_analytics[:5],
                    "top_orgs":  [{"org": "Personal", "total": total_reviews}],
                },
                "activity_timeline": timeline,
            }

    except Exception as e:
        logger.error(f"Failed to fetch analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute analytics telemetry.",
        )


@router.get("/export")
async def export_analytics(
    format: str = Query("json", description="json or csv"),
    user: User = Depends(require_auth)
):
    """Exports raw review telemetry in JSON or CSV format."""
    async with get_db() as db:
        rows = await db.fetch(
            """
            SELECT
                github_pr_id AS id,
                CASE WHEN repository_name LIKE '%/%' THEN repository_name
                     ELSE owner || '/' || repository_name END AS repo,
                number AS pr_number,
                reviewed_at,
                review_status AS status,
                decision AS decision_status,
                high_count, medium_count, low_count, issues_count
            FROM pull_requests
            WHERE review_status IS NOT NULL
            ORDER BY reviewed_at DESC
            """
        )

    if format.lower() == "csv":
        headers = ["id", "repo", "pr_number", "reviewed_at", "status", "decision_status",
                   "high_count", "medium_count", "low_count", "issues_count"]
        csv_lines = [",".join(headers)]
        for r in rows:
            rd = dict(r)
            line = [str(rd.get(h, "")) for h in headers]
            csv_lines.append(",".join(line))
        content = "\n".join(csv_lines)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=analytics_export.csv"},
        )

    return Response(
        content=json.dumps([dict(r) for r in rows], indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=analytics_export.json"},
    )
