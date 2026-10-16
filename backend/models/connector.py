from sqlalchemy import Column, String, BLOB, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base
import uuid

class ConnectorCredential(Base):
    __tablename__ = "connector_credentials"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    connector_id = Column(String(100), nullable=False)
    connector_type = Column(String(50), nullable=False)
    encrypted_credentials = Column(BLOB, nullable=False)
    status = Column(String(50), nullable=True)
    connected_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="connectors")
