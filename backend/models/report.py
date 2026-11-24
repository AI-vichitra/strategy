from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base
import uuid
from datetime import datetime

class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    message_id = Column(String(36), ForeignKey("messages.id"), nullable=True)
    agent_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    chart_count = Column(Integer, default=0)
    extracted_palette = Column(Text, nullable=True)  # JSON: {primary, secondary, accent} inferred by the agent
    # JSON: {truncated, stop_reason, provider, model, max_tokens, output_chars} — set ONLY when
    # generation was cut off by the provider's token limit (see ai_service.stream_chat). Null/absent
    # means the report completed normally; never written as a "false" value.
    truncation_info = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="reports")
