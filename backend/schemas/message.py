from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MessageBase(BaseModel):
    role: str
    content: str
    message_metadata: Optional[str] = None

class MessageCreate(MessageBase):
    project_id: str

class MessageResponse(MessageBase):
    id: str
    project_id: str
    created_at: datetime

    class Config:
        from_attributes = True
