from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional

from app.db.database import get_database
from app.core.security import get_current_user
from app.schemas.schemas import ChatRequest, ChatResponse, GenerateDraftRequest
from app.services import ai_service

router = APIRouter(prefix="/drafting", tags=["AI Drafting"])


def serialize_session(s: dict) -> dict:
    return {
        "id": str(s["_id"]),
        "user_id": str(s["user_id"]),
        "document_id": str(s["document_id"]) if s.get("document_id") else None,
        "messages": s.get("messages", []),
        "document_type": s.get("document_type"),
        "created_at": s["created_at"].isoformat(),
        "updated_at": s["updated_at"].isoformat(),
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Chat with AI to draft a legal document conversationally."""

    # Load or create session
    session = None
    session_id = data.session_id

    if session_id:
        try:
            session = await db.chat_sessions.find_one({
                "_id": ObjectId(session_id),
                "user_id": current_user["_id"],
            })
        except Exception:
            pass

    if not session:
        session = {
            "user_id": current_user["_id"],
            "document_id": ObjectId(data.document_id) if data.document_id else None,
            "messages": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = await db.chat_sessions.insert_one(session)
        session["_id"] = result.inserted_id
        session_id = str(result.inserted_id)

    # Build message history for API
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in session.get("messages", [])
    ]
    history.append({"role": "user", "content": data.message})

    # Get AI response
    user_profile = {
        "name": current_user.get("name"),
        "address": current_user.get("address"),
    }

    response_text, document_draft, missing_fields, action = await ai_service.chat_with_legal_ai(
        history, user_profile
    )

    # Save messages to session
    new_messages = [
        {
            "role": "user",
            "content": data.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    ]

    await db.chat_sessions.update_one(
        {"_id": session["_id"]},
        {
            "$push": {"messages": {"$each": new_messages}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        }
    )

    # If a draft was generated and document_id provided, update the document
    if document_draft and data.document_id:
        try:
            await db.documents.update_one(
                {"_id": ObjectId(data.document_id), "user_id": current_user["_id"]},
                {"$set": {"content": document_draft, "updated_at": datetime.now(timezone.utc)}}
            )
        except Exception:
            pass

    return ChatResponse(
        session_id=session_id,
        message=response_text,
        document_draft=document_draft,
        missing_fields=missing_fields,
        action=action,
    )


@router.post("/generate")
async def generate_document(
    data: GenerateDraftRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate a complete document from form data directly (non-chat flow)."""
    content = await ai_service.generate_document_from_data(
        document_type=data.document_type,
        filled_data=data.filled_data,
        additional_instructions=data.additional_instructions,
        jurisdiction=data.jurisdiction or "india",
    )

    # Save as a new document
    doc = {
        "user_id": current_user["_id"],
        "template_id": None,
        "title": f"AI-Generated {data.document_type}",
        "category": "ai_generated",
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

    return {
        "document_id": str(result.inserted_id),
        "content": content,
        "title": doc["title"],
    }


@router.get("/sessions")
async def list_sessions(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """List all chat sessions for current user."""
    cursor = db.chat_sessions.find(
        {"user_id": current_user["_id"]},
        {"messages": {"$slice": -1}}  # Only last message for preview
    ).sort("updated_at", -1).limit(20)

    sessions = []
    async for s in cursor:
        sessions.append({
            "id": str(s["_id"]),
            "last_message": s["messages"][-1]["content"][:100] if s.get("messages") else "",
            "created_at": s["created_at"].isoformat(),
            "updated_at": s["updated_at"].isoformat(),
        })
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get full chat session with all messages."""
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    session = await db.chat_sessions.find_one({"_id": oid, "user_id": current_user["_id"]})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return serialize_session(session)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Delete a chat session."""
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    await db.chat_sessions.delete_one({"_id": oid, "user_id": current_user["_id"]})
