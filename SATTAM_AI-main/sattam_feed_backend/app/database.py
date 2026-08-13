from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "sattam_feed_db"

client: AsyncIOMotorClient = None
db = None

async def connect_db():
    global client, db
    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    await client.admin.command("ping")
    print(f"✅ Connected to MongoDB: {DB_NAME}")

async def disconnect_db():
    global client
    if client:
        client.close()
        print("🔌 Disconnected from MongoDB")

def get_db():
    return db