from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ThreadCreateResponse(BaseModel):
    thread_id: str


class ThreadItem(BaseModel):
    thread_id: str
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ThreadTitleUpdate(BaseModel):
    title: str = Field(..., min_length=1, description="New title for the thread")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty or whitespace only")
        return stripped


class ChatMessageItem(BaseModel):
    id: int
    thread_id: str
    role: str
    content: str
    tool_name: Optional[str] = None
    created_at: Optional[datetime] = None


class ChatHistoryResponse(BaseModel):
    thread_id: str
    messages: list[ChatMessageItem]
