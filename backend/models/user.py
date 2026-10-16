from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base
import uuid
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    tier = Column(String, nullable=True)
    credits_remaining = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    brands = relationship("BrandConfig", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    connectors = relationship("ConnectorCredential", back_populates="user", cascade="all, delete-orphan")
