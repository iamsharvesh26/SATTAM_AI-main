from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router as gamification_router
from app.db import init_indexes
app = FastAPI(title="Sattam AI Gamification Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Gamification backend running (local MongoDB)"}

from app.db import db

@app.get("/test-db")
async def test_db():
    cols = await db.list_collection_names()
    return {"collections": cols}

app.include_router(gamification_router)

@app.on_event("startup")
async def startup_event():
    await init_indexes()