from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    timezone: str = "UTC"


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPreferencesSchema(BaseModel):
    default_market_id: Optional[str] = None
    min_ai_score: int = 70
    min_confidence: str = "MODERATE"
    allowed_risk_levels: List[str] = ["LOW", "MODERATE", "HIGH"]
    notify_on_all_signals: bool = True
    notify_on_status_change: bool = True
    notify_on_outcome: bool = True
    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    preferences: Optional[UserPreferencesSchema] = None
    is_telegram_linked: bool = False

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
