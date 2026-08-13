import os
from pymongo import ASCENDING
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "sattam_ai")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

users_col = db["gamification_users"]
events_col = db["gamification_events"]


async def init_indexes():
    await users_col.create_index([("user_id", ASCENDING)], unique=True)
    await events_col.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])


quizzes_col = db["quizzes"]
quiz_attempts_col = db["quiz_attempts"]

topics_col = db["topics"]
tracks_col = db["tracks"]