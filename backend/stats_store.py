# stats_store.py
import sqlite3
import os
import json
from datetime import datetime
from threading import Lock

DB_PATH = "reviews.db"
_lock = Lock()

def initialize_db():
    """Initializes the SQLite database with the required schema."""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # PRs Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                reviewed_at TEXT NOT NULL,
                bot_start_time TEXT NOT NULL
            )
        ''')

        # Issues Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_id INTEGER NOT NULL,
                severity TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                FOREIGN KEY (pr_id) REFERENCES prs (id)
            )
        ''')

        # System Meta Table (for persistent start time)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Set bot start time if not exists
        cursor.execute("INSERT OR IGNORE INTO system_meta (key, value) VALUES ('bot_start_time', ?)", (datetime.now().isoformat(),))

        conn.commit()
        conn.close()
        print(f"✅ SQLITE DATABASE INITIALIZED: {DB_PATH}")

def record_review(repo: str, pr_number: int, issues: list):
    """Saves review results to the SQLite database."""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get persistent bot start time for context (optional but keeps consistency)
        cursor.execute("SELECT value FROM system_meta WHERE key = 'bot_start_time'")
        bot_start = cursor.fetchone()[0]

        # Insert PR
        reviewed_at = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO prs (repo, pr_number, reviewed_at, bot_start_time) VALUES (?, ?, ?, ?)",
            (repo, pr_number, reviewed_at, bot_start)
        )
        pr_id = cursor.lastrowid

        # Insert Issues
        for issue in issues:
            cursor.execute(
                "INSERT INTO issues (pr_id, severity, type, description, file, line) VALUES (?, ?, ?, ?, ?, ?)",
                (pr_id, issue.get("severity", "low").lower(), issue.get("type", "bug").lower(),
                 issue.get("description", ""), issue.get("file", ""), issue.get("line", 0))
            )

        conn.commit()
        conn.close()
        print(f"📈 DATABASE RECORDED: {repo} #{pr_number} | {len(issues)} issues")

def get_stats() -> dict:
    """Aggregates all telemetry from the database."""
    with _lock:
        if not os.path.exists(DB_PATH):
            return {"total_prs": 0, "total_issues": 0, "uptime": "0h 0m 0s", "recent_reviews": []}

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Global Counts
        cursor.execute("SELECT COUNT(*) FROM prs")
        total_prs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM issues")
        total_issues = cursor.fetchone()[0]

        # Severity Breakdown
        cursor.execute("SELECT severity, COUNT(*) as count FROM issues GROUP BY severity")
        sev_data = {row['severity']: row['count'] for row in cursor.fetchall()}

        # Type Breakdown
        cursor.execute("SELECT type, COUNT(*) as count FROM issues GROUP BY type")
        type_data = {row['type']: row['count'] for row in cursor.fetchall()}

        # Recent Reviews (Last 10)
        cursor.execute("SELECT * FROM prs ORDER BY reviewed_at DESC LIMIT 10")
        prs = cursor.fetchall()

        recent_reviews = []
        for pr in prs:
            cursor.execute("SELECT * FROM issues WHERE pr_id = ?", (pr['id'],))
            issues = [dict(row) for row in cursor.fetchall()]

            # Formatted time
            dt = datetime.fromisoformat(pr['reviewed_at'])

            recent_reviews.append({
                "repo": pr['repo'],
                "pr_number": pr['pr_number'],
                "issue_count": len(issues),
                "reviewed_at": dt.strftime("%H:%M:%S"),
                "issues": issues,
                "severities": {
                    "high": sum(1 for i in issues if i['severity'] == "high"),
                    "medium": sum(1 for i in issues if i['severity'] == "medium"),
                    "low": sum(1 for i in issues if i['severity'] == "low"),
                }
            })

        # Uptime
        cursor.execute("SELECT value FROM system_meta WHERE key = 'bot_start_time'")
        bot_start_time = cursor.fetchone()[0]
        uptime_seconds = (datetime.now() - datetime.fromisoformat(bot_start_time)).total_seconds()
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        # Last Review Time
        cursor.execute("SELECT reviewed_at FROM prs ORDER BY reviewed_at DESC LIMIT 1")
        last_row = cursor.fetchone()
        last_review_time = last_row[0] if last_row else None

        conn.close()

        return {
            "total_prs": total_prs,
            "total_issues": total_issues,
            "issues_by_severity": {
                "high": sev_data.get("high", 0),
                "medium": sev_data.get("medium", 0),
                "low": sev_data.get("low", 0)
            },
            "issues_by_type": {
                "security": type_data.get("security", 0),
                "bug": type_data.get("bug", 0),
                "performance": type_data.get("performance", 0),
                "quality": type_data.get("quality", 0)
            },
            "recent_reviews": recent_reviews,
            "bot_status": "online",
            "uptime": f"{hours}h {minutes}m {seconds}s",
            "last_review_time": last_review_time
        }
