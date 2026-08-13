from fastapi import APIRouter, Depends, Query, HTTPException
from bson import ObjectId
from datetime import datetime
from app.database import get_db

router = APIRouter()

# ── Helper: convert MongoDB doc to clean dict ──────────────────
def format_case(case) -> dict:
    case["id"] = str(case["_id"])
    del case["_id"]
    return case


# ── GET /feed — paginated feed ─────────────────────────────────
@router.get("/")
async def get_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=50),
    db=Depends(get_db)
):
    skip = (page - 1) * limit
    cursor = db["case_feeds"].find().sort("published_at", -1).skip(skip).limit(limit)
    cases = []
    async for case in cursor:
        cases.append(format_case(case))
    return {
        "page": page,
        "limit": limit,
        "total": await db["case_feeds"].count_documents({}),
        "cases": cases
    }


# ── GET /feed/{id} — single case detail ───────────────────────
@router.get("/{id}")
async def get_case(id: str, db=Depends(get_db)):
    try:
        case = await db["case_feeds"].find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return format_case(case)


# ── POST /feed/{id}/like — toggle like ────────────────────────
@router.post("/{id}/like")
async def like_case(id: str, db=Depends(get_db)):
    try:
        result = await db["case_feeds"].update_one(
            {"_id": ObjectId(id)},
            {"$inc": {"likes": 1}}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"message": "Liked successfully"}


# ── POST /feed/{id}/save — toggle save ────────────────────────
@router.post("/{id}/save")
async def save_case(id: str, db=Depends(get_db)):
    try:
        result = await db["case_feeds"].update_one(
            {"_id": ObjectId(id)},
            {"$inc": {"saves": 1}}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"message": "Saved successfully"}


# ── GET /feed/filter/by — filter by type/court/state/tag ──────
@router.get("/filter/by")
async def filter_feed(
    type: str = Query(None),
    state: str = Query(None),
    tag: str = Query(None),
    court: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=50),
    db=Depends(get_db)
):
    query = {}
    if type:
        query["type"] = type.upper()
    if state:
        query["state"] = state
    if tag:
        query["tags"] = {"$in": [tag]}
    if court:
        query["court"] = {"$regex": court, "$options": "i"}

    skip = (page - 1) * limit
    cursor = db["case_feeds"].find(query).sort("published_at", -1).skip(skip).limit(limit)
    cases = []
    async for case in cursor:
        cases.append(format_case(case))
    return {
        "page": page,
        "limit": limit,
        "total": await db["case_feeds"].count_documents(query),
        "cases": cases
    }


# ── GET /feed/search/query — search by keyword ────────────────
@router.get("/search/query")
async def search_feed(
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=50),
    db=Depends(get_db)
):
    query = {"$text": {"$search": q}}
    skip = (page - 1) * limit
    cursor = db["case_feeds"].find(query).sort("published_at", -1).skip(skip).limit(limit)
    cases = []
    async for case in cursor:
        cases.append(format_case(case))
    return {
        "page": page,
        "limit": limit,
        "total": await db["case_feeds"].count_documents(query),
        "cases": cases
    }