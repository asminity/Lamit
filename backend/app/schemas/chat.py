from typing import Any
from pydantic import BaseModel, Field, field_validator


class ChatStreamRequest(BaseModel):
    thread_id: str = Field(..., min_length=1, description="Target thread ID")
    message: str = Field(..., min_length=1, description="User prompt")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty or whitespace only")
        return stripped


class ChatResumeRequest(BaseModel):
    thread_id: str = Field(..., min_length=1, description="Target thread ID")
    decision: Any = Field(..., description="Approval, input, or decision to resume run")
