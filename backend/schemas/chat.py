from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    project_id: str
    messages: List[ChatMessage]
    # No hardcoded default: a provider nobody picked must not pre-empt the
    # mode pin / key-presence selection. The chat UI always sends an explicit
    # value; when absent, None lets the server decide (advanced mode pins its
    # provider, standard mode selects by key presence).
    provider: Optional[str] = None
