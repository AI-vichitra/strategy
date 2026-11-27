from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base
import uuid
from datetime import datetime

def generate_uuid():
    return str(uuid.uuid4())

class Team(Base):
    """Team model - represents a workspace / organization"""
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)  # Team workspace logo / avatar
    admin_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    admin = relationship("User", foreign_keys=[admin_id], back_populates="owned_teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="team")
    brands = relationship("BrandConfig", back_populates="team")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "avatar_url": self.avatar_url,
            "admin_id": self.admin_id,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }

class TeamMember(Base):
    """Team Member model - links users to teams with roles"""
    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), default="member", nullable=False)  # 'admin', 'member'
    allowed_brands = Column(JSON, nullable=True)  # List of brand IDs (None/empty = all brands)
    allowed_projects = Column(JSON, nullable=True)  # List of project IDs (None/empty = all team projects)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")

    def to_dict(self):
        return {
            "id": self.id,
            "team_id": self.team_id,
            "user_id": self.user_id,
            "role": self.role,
            "allowed_brands": self.allowed_brands,
            "allowed_projects": self.allowed_projects,
            "joined_at": self.joined_at.isoformat() + "Z" if self.joined_at else None,
        }

class PendingInvitation(Base):
    """Pending team invitations"""
    __tablename__ = "pending_invitations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), nullable=False, index=True)
    invite_token = Column(String(255), nullable=False, index=True)
    invited_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    team_name = Column(String(255), nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # 'pending', 'accepted', 'expired', 'cancelled'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    metadata_json = Column(Text, nullable=True)  # JSON string for extra fields like role or allowed_brands

    invited_by = relationship("User", foreign_keys=[invited_by_user_id])
    team = relationship("Team", foreign_keys=[team_id])

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "invited_by_user_id": self.invited_by_user_id,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "status": self.status,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "expires_at": self.expires_at.isoformat() + "Z" if self.expires_at else None,
        }
