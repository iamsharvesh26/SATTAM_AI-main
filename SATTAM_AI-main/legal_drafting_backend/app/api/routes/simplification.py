from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from bson import ObjectId
from datetime import datetime, timezone
import aiofiles
import os
import uuid

from app.db.database import get_database
from app.core.security import get_current_user
from app.schemas.schemas import SimplifyRequest, SimplifyResponse
from app.services import ai_service
from app.core.config import settings

router = APIRouter(prefix="/simplify", tags=["Document Simplification"])


@router.post("", response_model=SimplifyResponse)
async def simplify_text(
    data: SimplifyRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Simplify legal text into plain language with key highlights."""
    result = await ai_service.simplify_legal_document(data.text, data.language or "english")

    doc = {
        "user_id": current_user["_id"],
        "original_text": data.text,
        "simplified_text": result.get("simplified_text", ""),
        "key_highlights": result.get("key_highlights", []),
        "legal_terms_explained": result.get("legal_terms_explained", {}),
        "risk_flags": result.get("risk_flags", []),
        "language": data.language,
        "created_at": datetime.now(timezone.utc),
    }

    result_db = await db.simplified_docs.insert_one(doc)
    doc["_id"] = result_db.inserted_id

    return SimplifyResponse(
        id=str(doc["_id"]),
        original_text=doc["original_text"],
        simplified_text=doc["simplified_text"],
        key_highlights=doc["key_highlights"],
        legal_terms_explained=doc["legal_terms_explained"],
        risk_flags=doc["risk_flags"],
        created_at=doc["created_at"],
    )


@router.post("/upload")
async def simplify_uploaded_document(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Upload a text/PDF document and simplify it."""
    allowed_types = ["text/plain", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only .txt and .pdf files are supported")

    # Save file temporarily
    ext = os.path.splitext(file.filename)[1]
    tmp_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB")

    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)

    # Extract text
    text = ""
    if file.content_type == "text/plain":
        text = content.decode("utf-8", errors="ignore")
    elif file.content_type == "application/pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(tmp_path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not extract PDF text: {str(e)}")

    os.remove(tmp_path)

    if len(text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Could not extract enough text from the document")

    # Truncate if too long
    text = text[:8000]

    result = await ai_service.simplify_legal_document(text)

    doc = {
        "user_id": current_user["_id"],
        "original_text": text,
        "simplified_text": result.get("simplified_text", ""),
        "key_highlights": result.get("key_highlights", []),
        "legal_terms_explained": result.get("legal_terms_explained", {}),
        "risk_flags": result.get("risk_flags", []),
        "filename": file.filename,
        "created_at": datetime.now(timezone.utc),
    }

    result_db = await db.simplified_docs.insert_one(doc)
    doc["_id"] = result_db.inserted_id

    return SimplifyResponse(
        id=str(doc["_id"]),
        original_text=doc["original_text"][:200] + "...",
        simplified_text=doc["simplified_text"],
        key_highlights=doc["key_highlights"],
        legal_terms_explained=doc["legal_terms_explained"],
        risk_flags=doc["risk_flags"],
        created_at=doc["created_at"],
    )


@router.get("/history")
async def simplification_history(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get user's simplification history."""
    cursor = db.simplified_docs.find(
        {"user_id": current_user["_id"]},
        {"original_text": {"$slice": 100}, "simplified_text": {"$slice": 200}}
    ).sort("created_at", -1).limit(20)

    history = []
    async for d in cursor:
        history.append({
            "id": str(d["_id"]),
            "original_preview": str(d.get("original_text", ""))[:150] + "...",
            "simplified_preview": str(d.get("simplified_text", ""))[:200] + "...",
            "key_highlights_count": len(d.get("key_highlights", [])),
            "created_at": d["created_at"].isoformat(),
        })
    return history


@router.get("/{simplification_id}")
async def get_simplification(
    simplification_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get a specific simplification result."""
    try:
        oid = ObjectId(simplification_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    doc = await db.simplified_docs.find_one({"_id": oid, "user_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")

    return SimplifyResponse(
        id=str(doc["_id"]),
        original_text=doc.get("original_text", ""),
        simplified_text=doc.get("simplified_text", ""),
        key_highlights=doc.get("key_highlights", []),
        legal_terms_explained=doc.get("legal_terms_explained", {}),
        risk_flags=doc.get("risk_flags", []),
        created_at=doc["created_at"],
    )
