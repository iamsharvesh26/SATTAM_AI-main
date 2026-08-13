from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    SHARED = "shared"
    ARCHIVED = "archived"


class DocumentCategory(str, Enum):
    AGREEMENTS = "agreements"
    PETITIONS = "petitions"
    AFFIDAVITS = "affidavits"
    NOTICES = "notices"
    COMPLAINTS = "complaints"


class ExportFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"


class Jurisdiction(str, Enum):
    INDIA = "india"
    TAMIL_NADU = "tamil_nadu"
    KARNATAKA = "karnataka"
    MAHARASHTRA = "maharashtra"
    DELHI = "delhi"


# ─── Auth Schemas ──────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    user_id: str
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(..., min_length=6)
    address: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v and not v.replace("+", "").replace("-", "").isdigit():
            raise ValueError("Invalid phone number")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


# ─── Template Schemas ──────────────────────────────────────────────────────────

class TemplateField(BaseModel):
    key: str
    label: str
    type: str  # text, textarea, date, number, select
    required: bool = True
    options: Optional[List[str]] = None  # for select type
    placeholder: Optional[str] = None


class TemplateResponse(BaseModel):
    id: str
    title: str
    category: str
    subcategory: Optional[str]
    jurisdiction: str
    language: str
    description: str
    tags: List[str]
    fields: List[Dict]
    is_free: bool
    created_at: datetime


class TemplateListResponse(BaseModel):
    id: str
    title: str
    category: str
    subcategory: Optional[str]
    jurisdiction: str
    language: str
    description: str
    tags: List[str]
    is_free: bool


# ─── Document (Draft) Schemas ──────────────────────────────────────────────────

class CreateDocumentRequest(BaseModel):
    template_id: str
    title: Optional[str] = None
    filled_data: Dict[str, Any] = {}


class UpdateDocumentRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    filled_data: Optional[Dict[str, Any]] = None
    status: Optional[DocumentStatus] = None


class DocumentVersion(BaseModel):
    version: int
    content: str
    updated_at: datetime
    note: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    template_id: Optional[str]
    title: str
    category: str
    content: str
    filled_data: Dict[str, Any]
    status: DocumentStatus
    versions: List[DocumentVersion] = []
    shared_with: List[str] = []
    created_at: datetime
    updated_at: datetime


# ─── Chat / AI Drafting Schemas ────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    document_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message: str
    document_draft: Optional[str] = None
    suggested_fields: Optional[Dict[str, Any]] = None
    missing_fields: Optional[List[str]] = None
    action: Optional[str] = None  # "request_info", "generate_draft", "finalize"


class GenerateDraftRequest(BaseModel):
    document_type: str
    filled_data: Dict[str, Any]
    additional_instructions: Optional[str] = None
    jurisdiction: Optional[str] = "india"
    language: Optional[str] = "english"


# ─── Simplification Schemas ────────────────────────────────────────────────────

class SimplifyRequest(BaseModel):
    text: str = Field(..., min_length=50)
    language: Optional[str] = "english"


class SimplifyResponse(BaseModel):
    id: str
    original_text: str
    simplified_text: str
    key_highlights: List[str]
    legal_terms_explained: Dict[str, str]
    risk_flags: List[str]
    created_at: datetime


# ─── Clause Schemas ────────────────────────────────────────────────────────────

class ClauseResponse(BaseModel):
    id: str
    title: str
    category: str
    content: str
    tags: List[str]


# ─── Export Schemas ────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    document_id: str
    format: ExportFormat


# ─── Share Schemas ─────────────────────────────────────────────────────────────

class ShareDocumentRequest(BaseModel):
    document_id: str
    recipient_emails: List[EmailStr]
    message: Optional[str] = None


# ─── Pagination ────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
