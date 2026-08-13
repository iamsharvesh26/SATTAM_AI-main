from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FeedType(str, Enum):
    BREAKING  = "BREAKING"
    LIVE      = "LIVE"
    JUDGMENT  = "JUDGMENT"
    VERDICT   = "VERDICT"
    ALERT     = "ALERT"

class CourtLevel(str, Enum):
    SUPREME   = "Supreme Court of India"
    HIGH      = "High Court"
    DISTRICT  = "District Court"
    NGT       = "National Green Tribunal"
    OTHER     = "Other"

class PredictiveStrategy(BaseModel):
    bail_likely: Optional[bool] = None
    confidence: Optional[float] = None
    summary: str
    sentencing_estimate: Optional[str] = None

class LegalSection(BaseModel):
    code: str
    section: str
    description: str

class CaseFeedCreate(BaseModel):
    type: FeedType
    court: str
    court_level: CourtLevel = CourtLevel.OTHER
    case_number: str
    state: Optional[str] = None
    title: str
    summary: str
    full_text: Optional[str] = None
    source_url: Optional[str] = None
    sections: List[LegalSection] = []
    bns_bridge: Optional[str] = None
    strategy: Optional[PredictiveStrategy] = None
    tags: List[str] = []
    published_at: datetime = Field(default_factory=datetime.utcnow)
    hearing_date: Optional[datetime] = None
    likes: int = 0
    saves: int = 0

class CaseFeedResponse(BaseModel):
    id: str
    type: FeedType
    court: str
    case_number: str
    state: Optional[str]
    title: str
    summary: str
    source_url: Optional[str]
    sections: List[LegalSection]
    bns_bridge: Optional[str]
    strategy: Optional[PredictiveStrategy]
    tags: List[str]
    published_at: datetime
    likes: int
    saves: int