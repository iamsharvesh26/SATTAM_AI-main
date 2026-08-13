import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import connect_db
from app.services.ingestion import fetch_and_store_cases

async def main():
    await connect_db()
    await fetch_and_store_cases()

if __name__ == "__main__":
    asyncio.run(main())