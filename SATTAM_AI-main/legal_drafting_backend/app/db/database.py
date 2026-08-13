from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings
from typing import Optional

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongo():
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    _db = _client[settings.MONGODB_DB_NAME]
    await create_indexes()
    print(f"✅ Connected to MongoDB: {settings.MONGODB_DB_NAME}")


async def close_mongo_connection():
    global _client
    if _client:
        _client.close()
        print("🔌 MongoDB connection closed")


async def get_database() -> AsyncIOMotorDatabase:
    return _db


async def create_indexes():
    """Create MongoDB indexes for performance."""

    # Users
    await _db.users.create_index("user_id", unique=True)  # Firebase UID
    await _db.users.create_index("email", unique=True)
    await _db.users.create_index("phone")

    # Templates
    await _db.templates.create_index("category")
    await _db.templates.create_index("jurisdiction")
    await _db.templates.create_index("language")
    await _db.templates.create_index(
        [("title", "text"), ("description", "text"), ("tags", "text")]
    )
    await _db.templates.create_index("is_active")

    # Documents (user drafts)
    await _db.documents.create_index("user_id")
    await _db.documents.create_index("template_id")
    await _db.documents.create_index("status")
    await _db.documents.create_index("created_at")

    # Chat sessions
    await _db.chat_sessions.create_index("user_id")
    await _db.chat_sessions.create_index("document_id")
    await _db.chat_sessions.create_index("created_at")

    # Clauses
    await _db.clauses.create_index("category")
    await _db.clauses.create_index([("title", "text"), ("content", "text")])

    # Simplified documents
    await _db.simplified_docs.create_index("user_id")
    await _db.simplified_docs.create_index("created_at")

    print("✅ MongoDB indexes created")