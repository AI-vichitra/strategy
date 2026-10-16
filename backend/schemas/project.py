from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    agent_type: str
    title: str
    description: Optional[str] = None
    questionnaire_answers: Optional[str] = None
    llm_provider: Optional[str] = "mistral"

class ProjectCreate(ProjectBase):
    brand_config_id: str

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    questionnaire_answers: Optional[str] = None
    llm_provider: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: str
    user_id: str
    brand_config_id: str
    llm_provider: Optional[str] = "mistral"
    last_active_at: Optional[datetime] = None
    created_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True
