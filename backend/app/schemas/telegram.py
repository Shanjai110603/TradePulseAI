from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class TelegramLinkCodeResponse(BaseModel):
    code: str
    expires_at: datetime
    bot_username: str
    deep_link: str
    instructions: str


class TelegramLinkRequest(BaseModel):
    code: str
    telegram_user_id: int
    telegram_chat_id: int
    telegram_username: Optional[str] = None
    first_name: Optional[str] = None


class TelegramStatusResponse(BaseModel):
    is_linked: bool
    telegram_username: Optional[str] = None
    telegram_chat_id: Optional[int] = None
    is_active: bool
    is_muted: bool
    muted_until: Optional[datetime] = None
    bot_username: str
    test_mode: bool
