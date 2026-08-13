from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import FileResponse
from bson import ObjectId
from typing import Optional
from datetime import datetime, timezone
import os

from app.db.database import get_database
from app.core.security import get_current_user
from app.schemas.schemas import (
    CreateDocumentRequest, UpdateDocumentRequest,
    ExportRequest, ExportFormat, ShareDocumentRequest
)
from app.services import ai_service, export_service

router = APIRouter(prefix="/documents", tags=["Documents"])


def serialize_doc(d: dict) -> dict:
    return {
        "id": str(d["_id"]),
        "user_id": str(d["user_id"]),
        "template_id": str(d["template_id"]) if d.get("template_id") else None,
        "title": d["title"],
        "category": d.get("category", ""),
        "content": d.get("content", ""),
        "filled_data": d.get("filled_data", {}),
        "status": d.get("status", "draft"),
        "versions": d.get("versions", []),
        "shared_with": d.get("shared_with", []),
        "risk_flags": d.get("risk_flags", []),
        "created_at": d["created_at"].isoformat(),
        "updated_at": d["updated_at"].isoformat(),
    }


@router.post("", status_code=201)
async def create_document(
    data: CreateDocumentRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Create a new document from a template."""
    template = None
    content = ""
    category = "general"

    if data.template_id:
        try:
            template = await db.templates.find_one({"_id": ObjectId(data.template_id)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid template ID")

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        category = template.get("category", "general")

        # Fill template body with provided data
        if data.filled_data and template.get("template_body"):
            content = template["template_body"]
            for key, value in data.filled_data.items():
                content = content.replace(f"{{{{{key}}}}}", str(value) if value else f"[{key.upper()}]")
        elif template.get("template_body"):
            content = template["template_body"]

    doc = {
        "user_id": current_user["_id"],
        "template_id": ObjectId(data.template_id) if data.template_id else None,
        "title": data.title or (template["title"] if template else "Untitled Document"),
        "category": category,
        "content": content,
        "filled_data": data.filled_data,
        "status": "draft",
        "versions": [],
        "shared_with": [],
        "risk_flags": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = await db.documents.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@router.get("")
async def list_documents(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """List current user's documents."""
    query = {"user_id": current_user["_id"]}
    if status:
        query["status"] = status
    if category:
        query["category"] = category

    total = await db.documents.count_documents(query)
    skip = (page - 1) * page_size
    cursor = db.documents.find(query).sort("updated_at", -1).skip(skip).limit(page_size)

    docs = []
    async for d in cursor:
        docs.append(serialize_doc(d))

    return {
        "items": docs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get a specific document."""
    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.documents.find_one({"_id": oid, "user_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return serialize_doc(doc)


@router.put("/{document_id}")
async def update_document(
    document_id: str,
    data: UpdateDocumentRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Update document content, title, or status. Auto-saves versions."""
    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.documents.find_one({"_id": oid, "user_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    update_fields: dict = {"updated_at": datetime.now(timezone.utc)}
    push_fields: dict = {}

    if data.title is not None:
        update_fields["title"] = data.title
    if data.status is not None:
        update_fields["status"] = data.status
    if data.filled_data is not None:
        update_fields["filled_data"] = data.filled_data

    # Version control: save previous content as a version
    if data.content is not None and data.content != doc.get("content", ""):
        current_versions = doc.get("versions", [])
        new_version = {
            "version": len(current_versions) + 1,
            "content": doc.get("content", ""),
            "updated_at": doc["updated_at"].isoformat() if isinstance(doc["updated_at"], datetime) else doc["updated_at"],
        }
        push_fields["versions"] = new_version
        update_fields["content"] = data.content

    update_op: dict = {"$set": update_fields}
    if push_fields:
        update_op["$push"] = push_fields

    await db.documents.update_one({"_id": oid}, update_op)

    updated = await db.documents.find_one({"_id": oid})
    return serialize_doc(updated)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Delete (archive) a document."""
    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.documents.update_one(
        {"_id": oid, "user_id": current_user["_id"]},
        {"$set": {"status": "archived", "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")


@router.post("/{document_id}/risk-check")
async def check_risks(
    document_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Run AI risk analysis on a document."""
    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.documents.find_one({"_id": oid, "user_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content = doc.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="Document has no content to analyze")

    risks = await ai_service.check_document_risks(content)

    await db.documents.update_one(
        {"_id": oid},
        {"$set": {"risk_flags": risks, "updated_at": datetime.now(timezone.utc)}}
    )

    return {"risk_flags": risks}


@router.post("/export")
async def export_document(
    data: ExportRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Export document as PDF or DOCX."""
    try:
        oid = ObjectId(data.document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.documents.find_one({"_id": oid, "user_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content = doc.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="Document has no content to export")

    title = doc.get("title", "Legal Document")
    author = current_user.get("name")

    if data.format == ExportFormat.PDF:
        filepath = export_service.export_to_pdf(content, title, author)
        media_type = "application/pdf"
        ext = "pdf"
    else:
        filepath = export_service.export_to_docx(content, title, author)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = "docx"

    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").replace(" ", "_")
    download_name = f"{safe_title}.{ext}"

    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=download_name,
        background=BackgroundTasks(),
    )


@router.post("/{document_id}/share")
async def share_document(
    document_id: str,
    data: ShareDocumentRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Share document with others (by email)."""
    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.documents.find_one({"_id": oid, "user_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.documents.update_one(
        {"_id": oid},
        {
            "$addToSet": {"shared_with": {"$each": data.recipient_emails}},
            "$set": {"status": "shared", "updated_at": datetime.now(timezone.utc)},
        }
    )

    return {"message": f"Document shared with {len(data.recipient_emails)} recipient(s)", "recipients": data.recipient_emails}


@router.get("/{document_id}/versions")
async def get_versions(
    document_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get version history of a document."""
    try:
        oid = ObjectId(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.documents.find_one(
        {"_id": oid, "user_id": current_user["_id"]},
        {"versions": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"versions": doc.get("versions", [])}
