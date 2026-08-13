import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import connect_db, get_db

async def main():
    await connect_db()
    db = get_db()

    await db["case_feeds"].create_index("published_at")
    await db["case_feeds"].create_index("type")
    await db["case_feeds"].create_index([("tags", 1)])
    await db["case_feeds"].create_index([("court", 1)])
    await db["case_feeds"].create_index(
        [("title", "text"), ("summary", "text")]
    )
    print("✅ All indexes created!")

if __name__ == "__main__":
    asyncio.run(main())