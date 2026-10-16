from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base
import uuid
from datetime import datetime

class BrandConfig(Base):
    __tablename__ = "brand_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    brand_name = Column(String, nullable=False)
    website_url = Column(String, nullable=True)
    category = Column(String, nullable=False)
    brand_context = Column(Text, nullable=True)
    competitors = Column(Text, nullable=True)          # JSON list of {name, url}
    social_metrics = Column(Text, nullable=True)       # Kept for backwards compat / status signals
    # New pipeline tracking columns
    brand_slug = Column(String, nullable=True)         # Docs folder name: brand_name_id[:8]
    brand_handle = Column(String, nullable=True)       # Discovered Instagram handle
    confirmed_competitor_handles = Column(Text, nullable=True)  # JSON list of handles
    pipeline_status = Column(String, default="pending", nullable=False)  # pending | running | complete | failed
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="brands")
    projects = relationship("Project", back_populates="brand", cascade="all, delete-orphan")
