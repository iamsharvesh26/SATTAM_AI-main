from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from typing import Optional
from app.db.database import get_database
from app.core.security import get_current_user

router = APIRouter(prefix="/clauses", tags=["Clause Library"])


def serialize_clause(c: dict) -> dict:
    return {
        "id": str(c["_id"]),
        "title": c["title"],
        "category": c["category"],
        "content": c["content"],
        "tags": c.get("tags", []),
    }


@router.get("")
async def list_clauses(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user=Depends(get_current_user),
):
    """List all available clauses."""
    query: dict = {"is_active": True}
    if category:
        query["category"] = category
    if search:
        query["$text"] = {"$search": search}

    clauses = []
    async for c in db.clauses.find(query):
        clauses.append(serialize_clause(c))
    return clauses


@router.get("/categories")
async def clause_categories(db=Depends(get_database), current_user=Depends(get_current_user)):
    """Get all clause categories."""
    pipeline = [
        {"$match": {"is_active": True}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    ]
    result = []
    async for doc in db.clauses.aggregate(pipeline):
        result.append({"category": doc["_id"], "count": doc["count"]})
    return result


@router.get("/{clause_id}")
async def get_clause(clause_id: str, db=Depends(get_database), current_user=Depends(get_current_user)):
    """Get a specific clause."""
    try:
        oid = ObjectId(clause_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid clause ID")

    clause = await db.clauses.find_one({"_id": oid})
    if not clause:
        raise HTTPException(status_code=404, detail="Clause not found")

    return serialize_clause(clause)


@router.post("/{clause_id}/add-to-document/{document_id}")
async def add_clause_to_document(
    clause_id: str,
    document_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Append a clause to an existing document."""
    try:
        clause = await db.clauses.find_one({"_id": ObjectId(clause_id)})
        doc = await db.documents.find_one({
            "_id": ObjectId(document_id),
            "user_id": current_user["_id"]
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID(s)")

    if not clause:
        raise HTTPException(status_code=404, detail="Clause not found")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    clause_text = f"\n\n{clause['title'].upper()}\n{clause['content']}"
    new_content = doc.get("content", "") + clause_text

    from datetime import datetime, timezone
    await db.documents.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {"content": new_content, "updated_at": datetime.now(timezone.utc)}}
    )

    return {"message": f"Clause '{clause['title']}' added to document", "added_text": clause_text}
