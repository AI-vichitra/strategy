from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
import json

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class CompetitorSocialMedia(BaseModel):
    linkedin: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None

class CompetitorDetail(BaseModel):
    brand_name: str
    website_url: Optional[str] = None
    social_media: Optional[CompetitorSocialMedia] = None

class CompetitorDetailsInput(BaseModel):
    competitors: List[CompetitorDetail] = []  # Max 5

class ProjectBase(BaseModel):
    agent_type: str
    title: str
    description: Optional[str] = None
    questionnaire_answers: Optional[str] = None
    llm_provider: Optional[str] = "mistral"
    competitor_details: Optional[List[CompetitorDetail]] = None

class ProjectCreate(ProjectBase):
    brand_config_id: str

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    questionnaire_answers: Optional[str] = None
    llm_provider: Optional[str] = None
    competitor_details: Optional[List[CompetitorDetail]] = None

class ProjectResponse(BaseModel):
    id: str
    user_id: str
    brand_config_id: str
    agent_type: str
    title: str
    description: Optional[str] = None
    questionnaire_answers: Optional[str] = None
    llm_provider: Optional[str] = "mistral"
    competitor_details: Optional[List[CompetitorDetail]] = None
    last_active_at: Optional[datetime] = None
    created_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True

    @field_validator("competitor_details", mode="before")
    @classmethod
    def _parse_competitor_details(cls, value):
        # Stored on the Project ORM row as a raw JSON string (Text column);
        # parse it back into structured objects for the API response.
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str):
            if not value.strip():
                return None
            return json.loads(value)
        return value
