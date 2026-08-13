# app/routes/user.py

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime, timezone
from app.database import get_db

router = APIRouter()


def _uid(x_user_id: str = Header(..., alias="X-User-ID")) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header missing")
    return x_user_id


def _fmt(case) -> dict:
    case["id"] = str(case["_id"])
    del case["_id"]
    return case


# ── Request body for sync ──────────────────────────────────────
class SyncRequest(BaseModel):
    name: str = ""
    email: str = ""


# ── POST /user/sync ────────────────────────────────────────────
@router.post("/sync")
async def sync_user(
    body: SyncRequest,
    uid: str = Depends(_uid),
    db=Depends(get_db),
):
    existing = await db["users"].find_one({"uid": uid})
    if existing:
        # Update name/email in case they changed
        await db["users"].update_one(
            {"uid": uid},
            {"$set": {"name": body.name, "email": body.email}},
        )
        return {"status": "updated"}

    await db["users"].insert_one({
        "uid": uid,
        "name": body.name,
        "email": body.email,
        "liked_cases": [],
        "saved_cases": [],
        "created_at": datetime.now(timezone.utc),
    })
    return {"status": "created"}


# ── POST /user/like/{case_id} ──────────────────────────────────
@router.post("/like/{case_id}")
async def toggle_like(
    case_id: str,
    uid: str = Depends(_uid),
    db=Depends(get_db),
):
    user = await db["users"].find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Call /sync first.")

    is_liked = case_id in user.get("liked_cases", [])

    if is_liked:
        await db["users"].update_one({"uid": uid}, {"$pull": {"liked_cases": case_id}})
        await db["case_feeds"].update_one({"_id": ObjectId(case_id)}, {"$inc": {"likes": -1}})
        return {"liked": False, "message": "Unliked"}
    else:
        await db["users"].update_one({"uid": uid}, {"$addToSet": {"liked_cases": case_id}})
        await db["case_feeds"].update_one({"_id": ObjectId(case_id)}, {"$inc": {"likes": 1}})
        return {"liked": True, "message": "Liked"}


# ── POST /user/save/{case_id} ──────────────────────────────────
@router.post("/save/{case_id}")
async def toggle_save(
    case_id: str,
    uid: str = Depends(_uid),
    db=Depends(get_db),
):
    user = await db["users"].find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Call /sync first.")

    is_saved = case_id in user.get("saved_cases", [])

    if is_saved:
        await db["users"].update_one({"uid": uid}, {"$pull": {"saved_cases": case_id}})
        await db["case_feeds"].update_one({"_id": ObjectId(case_id)}, {"$inc": {"saves": -1}})
        return {"saved": False, "message": "Unsaved"}
    else:
        await db["users"].update_one({"uid": uid}, {"$addToSet": {"saved_cases": case_id}})
        await db["case_feeds"].update_one({"_id": ObjectId(case_id)}, {"$inc": {"saves": 1}})
        return {"saved": True, "message": "Saved"}


# ── GET /user/profile ──────────────────────────────────────────
@router.get("/profile")
async def get_profile(
    uid: str = Depends(_uid),
    db=Depends(get_db),
):
    user = await db["users"].find_one({"uid": uid})
    if not user:
        await db["users"].insert_one({
            "uid": uid, "name": "", "email": "",
            "liked_cases": [], "saved_cases": [],
            "created_at": datetime.now(timezone.utc),
        })
        return {"liked_cases": [], "saved_cases": []}

    liked_cases, saved_cases = [], []
    for cid in user.get("liked_cases", []):
        try:
            doc = await db["case_feeds"].find_one({"_id": ObjectId(cid)})
            if doc: liked_cases.append(_fmt(doc))
        except Exception:
            pass
    for cid in user.get("saved_cases", []):
        try:
            doc = await db["case_feeds"].find_one({"_id": ObjectId(cid)})
            if doc: saved_cases.append(_fmt(doc))
        except Exception:
            pass

    return {"liked_cases": liked_cases, "saved_cases": saved_cases}


# ── GET /user/state ────────────────────────────────────────────
@router.get("/state")
async def get_user_state(
    uid: str = Depends(_uid),
    db=Depends(get_db),
):
    user = await db["users"].find_one({"uid": uid})
    if not user:
        return {"liked_cases": [], "saved_cases": []}
    return {
        "liked_cases": user.get("liked_cases", []),
        "saved_cases": user.get("saved_cases", []),
    }