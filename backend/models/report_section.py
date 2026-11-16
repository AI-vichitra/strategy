from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from backend.database import Base
from datetime import datetime


class ReportSection(Base):
    __tablename__ = "report_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # reports.id is a String(36) UUID, so the FK follows that type rather than Integer.
    report_id = Column(String(36), ForeignKey("reports.id"), nullable=False, index=True)
    order = Column(Integer, nullable=False)
    section_type = Column(String(20), nullable=False)  # heading | text | table | chart
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    visible = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_report_sections_report_id_order", "report_id", "order"),
    )
