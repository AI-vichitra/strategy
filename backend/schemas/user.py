from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserCreate(UserBase):
    password: str
    invite_token: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserResponse(UserBase):
    id: str
    tier: Optional[str] = "free"
    credits_remaining: Optional[int] = 0
    role: Optional[str] = "admin"
    parent_user_id: Optional[str] = None
    team_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
