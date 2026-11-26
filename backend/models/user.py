from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
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
    avatar_url = Column(String, nullable=True)
    tier = Column(String, nullable=True)
    credits_remaining = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Password reset fields
    reset_token = Column(String(255), nullable=True)
    reset_token_created_at = Column(DateTime, nullable=True)

    # Team & role hierarchy
    role = Column(String(20), default="admin", nullable=False)  # 'admin' or 'member'
    parent_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    team_name = Column(String(255), nullable=True)

    brands = relationship("BrandConfig", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    connectors = relationship("ConnectorCredential", back_populates="user", cascade="all, delete-orphan")
    team_memberships = relationship("TeamMember", back_populates="user", cascade="all, delete-orphan")
    owned_teams = relationship("Team", back_populates="admin", foreign_keys="[Team.admin_id]")
