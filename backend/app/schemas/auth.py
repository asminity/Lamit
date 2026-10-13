from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class UserSignupRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")
    name: Optional[str] = Field(None, description="User full display name")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        stripped = v.strip().lower()
        if "@" not in stripped or "." not in stripped:
            raise ValueError("Invalid email address format")
        return stripped

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v.strip()) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        stripped = v.strip().lower()
        if not stripped:
            raise ValueError("Email cannot be empty")
        return stripped


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    auth_provider: str = "local"
    created_at: Optional[datetime] = None


class GoogleVerifyRequest(BaseModel):
    credential: str = Field(..., min_length=1, description="Google ID Token credential")
