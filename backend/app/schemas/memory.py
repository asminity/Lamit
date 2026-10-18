from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    PROFILE = "profile"
    PREFERENCE = "preference"
    EPISODIC = "episodic"
    SEMANTIC_FACT = "semantic_fact"
    PROJECT_KNOWLEDGE = "project_knowledge"


class MemoryItem(BaseModel):
    id: int
    user_id: str
    memory_type: str
    content: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    importance: float = 0.5
    confidence: float = 1.0
    provenance: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    superseded_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    similarity_score: Optional[float] = None


class MemoryCreateRequest(BaseModel):
    memory_type: MemoryType = MemoryType.SEMANTIC_FACT
    content: str = Field(..., min_length=1, max_length=2000)
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    structured_data: Optional[Dict[str, Any]] = None
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None


class ExtractedMemory(BaseModel):
    memory_type: MemoryType
    content: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    supersedes_key: Optional[str] = None  # key in structured_data or semantic keyword that this supersedes


class MemoryListResponse(BaseModel):
    memories: List[MemoryItem]
    total: int
