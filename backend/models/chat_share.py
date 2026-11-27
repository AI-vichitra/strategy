from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.database import Base
import uuid
from datetime import datetime

class ChatShare(Base):
    """
    Stores shared snapshot links of chat conversations (projects).
    Snapshots are lightweight, self-contained JSON records of messages up until the share time.
    """
    __tablename__ = "chat_shares"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    owner_name = Column(String(255), nullable=True)
    owner_email = Column(String(255), nullable=True)
    access_type = Column(String(20), default="anyone", nullable=False)  # 'anyone' | 'invited'
    invited_emails = Column(JSON, default=list, nullable=False)  # List of emails allowed to view
    access_requests = Column(JSON, default=list, nullable=False)  # List of {email, requested_at, status}
    snapshot_messages = Column(JSON, default=list, nullable=False)  # Lightweight message items
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # 3 days validity from generation/refresh
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", backref="shares")
    user = relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "title": self.title,
            "owner_name": self.owner_name,
            "owner_email": self.owner_email,
            "access_type": self.access_type,
            "invited_emails": self.invited_emails or [],
            "access_requests": self.access_requests or [],
            "snapshot_messages": self.snapshot_messages or [],
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() + "Z" if self.expires_at else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }
