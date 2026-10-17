from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class CacheLookupResult(BaseModel):
    hit: bool = False
    cached_response: Optional[str] = None
    similarity_score: Optional[float] = None
    matched_query: Optional[str] = None
    cache_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CacheEntryCreate(BaseModel):
    user_id: str
    query_text: str
    response_text: str
    embedding: List[float]
    model_name: Optional[str] = None
    embedding_model: Optional[str] = None
    config_version: Optional[str] = "v1"
    scope: str = "private"
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CacheStats(BaseModel):
    total_entries: int = 0
    active_user_entries: int = 0
    expired_entries: int = 0
