import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# FIX: Using synchronous PyMongo (your rag_service uses sync .find_one/.update_one)
# This is CORRECT for your current code. Keep it sync.
# If you move to async FastAPI background tasks later, switch to Motor.

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client["legal_ai_db"]

# Collections
chat_sessions = db["chat_sessions"]
documents_meta = db["documents_meta"]

# FIX: Create indexes on startup for query performance
# Without indexes, find_one({"session_id": ...}) does a full collection scan
chat_sessions.create_index("session_id", unique=True, sparse=True)
chat_sessions.create_index("user_id")
documents_meta.create_index("document_id", unique=True, sparse=True)
documents_meta.create_index("user_id")