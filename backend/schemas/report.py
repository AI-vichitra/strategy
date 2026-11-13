from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReportMetadata(BaseModel):
    id: str
    message_id: Optional[str] = None
    version: int
    title: str
    agent_type: str
    chart_count: int
    created_at: datetime

    class Config:
        from_attributes = True

class ReportDetail(ReportMetadata):
    project_id: str
    content: str

class ShareTokenResponse(BaseModel):
    token: str

class ExportDocxRequest(BaseModel):
    content: Optional[str] = None

class PublicReport(BaseModel):
    title: str
    content: str
    agent_type: str
    brand_name: Optional[str] = None
    created_at: datetime
