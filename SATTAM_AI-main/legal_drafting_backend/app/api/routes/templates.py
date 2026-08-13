from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from typing import Optional, List
from app.db.database import get_database
from app.core.security import get_current_user, get_optional_user

router = APIRouter(prefix="/templates", tags=["Templates"])


def serialize_template(t: dict, full: bool = False) -> dict:
    base = {
        "id": str(t["_id"]),
        "title": t["title"],
        "category": t["category"],
        "subcategory": t.get("subcategory"),
        "jurisdiction": t["jurisdiction"],
        "language": t["language"],
        "description": t["description"],
        "tags": t.get("tags", []),
        "is_free": t.get("is_free", True),
    }
    if full:
        base["fields"] = t.get("fields", [])
        base["template_body"] = t.get("template_body", "")
        base["created_at"] = t.get("created_at", "").isoformat() if t.get("created_at") else None
    return base


@router.get("")
async def list_templates(
    category: Optional[str] = Query(None),
    jurisdiction: Optional[str] = Query(None),
    language: Optional[str] = Query("english"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_database),
):
    """List all templates with optional filters."""
    query: dict = {"is_active": True}

    if category:
        query["category"] = category
    if jurisdiction:
        query["jurisdiction"] = jurisdiction
    if language:
        query["language"] = language
    if search:
        query["$text"] = {"$search": search}

    total = await db.templates.count_documents(query)
    skip = (page - 1) * page_size

    cursor = db.templates.find(query).skip(skip).limit(page_size)
    templates = []
    async for t in cursor:
        templates.append(serialize_template(t, full=False))

    return {
        "items": templates,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/categories")
async def get_categories(db=Depends(get_database)):
    """Get all available categories with counts."""
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    result = []
    async for doc in db.templates.aggregate(pipeline):
        result.append({"category": doc["_id"], "count": doc["count"]})
    return result


@router.get("/{template_id}")
async def get_template(template_id: str, db=Depends(get_database)):
    """Get full template details including fields and body."""
    try:
        oid = ObjectId(template_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid template ID")

    template = await db.templates.find_one({"_id": oid, "is_active": True})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return serialize_template(template, full=True)


@router.get("/{template_id}/preview")
async def preview_template(template_id: str, db=Depends(get_database)):
    """Get template body preview without sensitive field data."""
    try:
        oid = ObjectId(template_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid template ID")

    template = await db.templates.find_one({"_id": oid, "is_active": True})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "id": str(template["_id"]),
        "title": template["title"],
        "preview": template.get("template_body", "")[:500] + "...",
        "fields": template.get("fields", []),
    }
