from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    project_id: str
    messages: List[ChatMessage]
    provider: Optional[str] = "qwen"
