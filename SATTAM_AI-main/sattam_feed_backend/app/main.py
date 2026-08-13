# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import connect_db, disconnect_db
from app.routes.feed import router as feed_router
from app.routes.user import router as user_router
from app.routes.admin_router import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await disconnect_db()


app = FastAPI(
    title="SATTAM AI — Legal Feed API",
    description="Backend for the Case & Crime Feed module",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "SATTAM AI Feed API"}


# ── Routes ─────────────────────────────────────────────────────
app.include_router(feed_router, prefix="/api/v1/feed", tags=["Feed"])
app.include_router(user_router, prefix="/api/v1/user", tags=["User"])
app.include_router(admin_router, prefix="/api/v1", tags=["Admin"])