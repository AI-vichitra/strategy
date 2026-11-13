from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from backend.database import Base
import uuid
from datetime import datetime

class ReportShare(Base):
    __tablename__ = "report_shares"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey("reports.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
