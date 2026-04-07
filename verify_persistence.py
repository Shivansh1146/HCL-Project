import sys
import os
# Add current directory to path to find stats_store
sys.path.append(os.path.abspath(os.curdir))
from backend.stats_store import initialize_db, record_review, get_stats

# 1. Initialize
initialize_db()

# 2. Record a dummy review
print("--- Recording Sample Review ---")
record_review("Verify/Persistence", 101, [
    {"severity": "high", "type": "security", "description": "Persistence Test High", "file": "test.py", "line": 10},
    {"severity": "medium", "type": "bug", "description": "Persistence Test Med", "file": "test.py", "line": 20}
])

# 3. Get Stats
stats = get_stats()
print(f"Total PRs: {stats['total_prs']}")
print(f"Total Issues: {stats['total_issues']}")
print(f"Recent PRs: {[r['repo'] for r in stats['recent_reviews']]}")

# 4. Verify specific record
if stats['total_prs'] > 0:
    print("✅ PERSISTENCE VERIFIED: Data successfully written and retrieved from SQLite.")
else:
    print("❌ PERSISTENCE FAILED: No data found.")
