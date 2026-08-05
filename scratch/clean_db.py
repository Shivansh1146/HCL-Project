import asyncio
import os
import sys

# Add backend to sys.path to import stats_store
sys.path.append(os.path.join(os.getcwd(), "backend"))

from stats_store import clear_db

async def main():
    print("🧹 Cleaning database...")
    await clear_db()
    print("✅ Database cleaned successfully.")

if __name__ == "__main__":
    asyncio.run(main())
