from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    tier: Optional[str] = "free"
    credits_remaining: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True
