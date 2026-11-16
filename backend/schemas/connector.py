from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ConnectorCredentialCreate(BaseModel):
    connector_id: str
    connector_type: str
    credentials: Dict[str, Any] = {}


class ConnectorCredentialResponse(BaseModel):
    connector_id: str
    connector_type: str
    status: Optional[str] = None
    connected_at: Optional[datetime] = None

    class Config:
        from_attributes = True
