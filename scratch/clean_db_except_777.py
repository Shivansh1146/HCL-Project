import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from stats_store import get_db

async def main():
    print("[CLEAN] Cleaning database (keeping PR #777)...")
    async with get_db() as db:
        # Find the internal row id(s) for pr_number=777 to preserve their issues
        async with db.execute("SELECT id FROM prs WHERE pr_number = 777") as cursor:
            pr777_rows = await cursor.fetchall()
        keep_ids = [row[0] for row in pr777_rows]
        print(f"  [INFO] Preserving internal PR row id(s) for #777: {keep_ids}")

        # Delete issues NOT linked to PR #777
        if keep_ids:
            placeholders = ",".join("?" * len(keep_ids))
            await db.execute(f"DELETE FROM issues WHERE pr_id NOT IN ({placeholders})", keep_ids)
            await db.execute(f"DELETE FROM prs WHERE id NOT IN ({placeholders})", keep_ids)
        else:
            # PR #777 not in DB -- wipe everything
            print("  [WARN] PR #777 not found. Wiping all records.")
            await db.execute("DELETE FROM issues")
            await db.execute("DELETE FROM prs")

        # Clear all processed SHAs so webhooks can be re-triggered
        await db.execute("DELETE FROM processed_shas")
        await db.commit()

    print("[DONE] Database cleaned. PR #777 preserved.")

if __name__ == "__main__":
    asyncio.run(main())
