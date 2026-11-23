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
    # Raw JSON string ({truncated, stop_reason, provider, model, max_tokens,
    # output_chars}), set only when generation was cut off by the provider's
    # token limit (see ai_service.stream_chat). None for a normal, complete
    # report — never a literal "false".
    truncation_info: Optional[str] = None

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
