from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime, timezone
from bson import ObjectId
from app.schemas.schemas import UserRegister, UserLogin, TokenResponse, RefreshTokenRequest, UserProfile
from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token,
    decode_token, get_current_user
)
from app.db.database import get_database

router = APIRouter(prefix="/auth", tags=["Authentication"])


def serialize_user(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "phone": user.get("phone"),
        "address": user.get("address"),
        "created_at": user.get("created_at", "").isoformat() if user.get("created_at") else None,
    }


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db=Depends(get_database)):
    """Register a new user."""
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user_doc = {
        "user_id": data.user_id,
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
        "address": data.address,
        "password_hash": get_password_hash(data.password),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    access_token = create_access_token({"sub": str(result.inserted_id)})
    refresh_token = create_refresh_token({"sub": str(result.inserted_id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=serialize_user(user_doc),
    )


# In register, user_id is already saved ✅
# In login, add firebase_uid lookup as fallback:
@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db=Depends(get_database)):
    user = await db.users.find_one({"email": data.email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")


    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    access_token = create_access_token({"sub": str(user["_id"])})
    refresh_token = create_refresh_token({"sub": str(user["_id"])})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=serialize_user(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshTokenRequest, db=Depends(get_database)):
    """Refresh access token using refresh token."""
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_access_token({"sub": str(user["_id"])})
    new_refresh_token = create_refresh_token({"sub": str(user["_id"])})

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=serialize_user(user),
    )


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    """Get current user profile."""
    return serialize_user(current_user)


@router.put("/me")
async def update_profile(data: UserProfile, current_user=Depends(get_current_user), db=Depends(get_database)):
    """Update user profile."""
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)

    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": update_data}
    )

    updated = await db.users.find_one({"_id": current_user["_id"]})
    return serialize_user(updated)
