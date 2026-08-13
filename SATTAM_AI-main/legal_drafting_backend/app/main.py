from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.database import connect_to_mongo, close_mongo_connection
from app.api.routes import auth, templates, documents, drafting, simplification, clauses


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Legal Document Simplification & Drafting API
**Module 4: Legal Drafting Library** | RAAM TECHLINK Pvt Ltd

### Features
- 🔐 **JWT Authentication** - Register, login, refresh tokens
- 📄 **Template Library** - Pre-drafted legal templates (NDA, Rent Agreement, etc.)
- 🤖 **AI Drafting Chatbot** - Conversational document drafting via Claude AI
- ✏️ **Document Editor** - CRUD with version control
- 📝 **Document Simplification** - Plain language summaries with key highlights
- ⚖️ **Clause Library** - Reusable legal clauses
- 📤 **Export** - PDF and Word (.docx) download
- 🔗 **Share** - Share documents with lawyers or friends

### Authentication
All protected endpoints require `Authorization: Bearer <token>` header.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ─── Routes ───────────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(templates.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(drafting.router, prefix=API_PREFIX)
app.include_router(simplification.router, prefix=API_PREFIX)
app.include_router(clauses.router, prefix=API_PREFIX)


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "company": "RAAM TECHLINK Pvt Ltd",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}
