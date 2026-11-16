from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ReportSectionResponse(BaseModel):
    id: int
    report_id: str
    order: int
    section_type: str
    title: Optional[str] = None
    content: str
    visible: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SectionCreateRequest(BaseModel):
    after_order: int
    title: Optional[str] = None
    content: str
    section_type: str


class SectionUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    visible: Optional[bool] = None


class SectionReorderRequest(BaseModel):
    section_ids: List[int]
