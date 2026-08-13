from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class CreateUserIn(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)

class UserOut(BaseModel):
    user_id: str
    name: str
    points: int
    level: int
    streak: int
    badges: List[str] = []

class AwardIn(BaseModel):
    user_id: str
    points: int = Field(..., ge=1)
    reason: Optional[str] = None
    event_type: str = "award"
    meta: Dict[str, Any] = {}


from typing import List
from pydantic import BaseModel, Field


class QuizAnswer(BaseModel):
    question_id: str
    selected_option: str


class QuizSubmitIn(BaseModel):
    user_id: str
    quiz_id: str
    answers: List[QuizAnswer] = Field(..., min_items=1)