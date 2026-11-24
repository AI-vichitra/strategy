from sqlalchemy import Column, String, Text, DateTime, ForeignKey, LargeBinary
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base
import uuid
from datetime import datetime

# Imported so SQLAlchemy's mapper registry can resolve the "Report" string
# in the relationship below before any query runs.
from backend.models.report import Report  # noqa: F401

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    brand_config_id = Column(String(36), ForeignKey("brand_configs.id"), nullable=False)
    agent_type = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    questionnaire_answers = Column(Text, nullable=True)
    competitor_details = Column(Text, nullable=True)  # JSON string: list of competitor objects
    brand_kit = Column(Text, nullable=True)  # JSON: {logo_url, colors:{primary,secondary,accent}, extracted_palette}
    logo_data = Column(LargeBinary, nullable=True)  # Raw logo bytes, mirrored from brand_kit.logo_url's file; DB is source of truth, file is local cache
    logo_mime = Column(String(100), nullable=True)  # MIME type of logo_data
    llm_provider = Column(String(50), nullable=True, default="openai")
    last_active_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="projects")
    brand = relationship("BrandConfig", back_populates="projects")
    messages = relationship("Message", back_populates="project", cascade="all, delete-orphan", lazy="selectin")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan", lazy="selectin")
