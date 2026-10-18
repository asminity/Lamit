from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.schemas.memory import (
    MemoryItem,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemoryListResponse,
)
from backend.app.services.memory_service import memory_service

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=MemoryListResponse)
async def list_user_memories(
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    is_active: bool = Query(True, description="Filter active vs archived memories"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Lists long-term memories for the authenticated user."""
    memories = await memory_service.list_memories(
        user_id=current_user.user_id,
        memory_type=memory_type,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return MemoryListResponse(memories=memories, total=len(memories))


@router.post("", response_model=MemoryItem, status_code=status.HTTP_201_CREATED)
async def create_user_memory(
    body: MemoryCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Explicitly stores a user memory."""
    memory = await memory_service.add_memory(
        user_id=current_user.user_id,
        memory_type=body.memory_type.value,
        content=body.content,
        structured_data=body.structured_data,
        importance=body.importance,
        confidence=body.confidence,
        provenance={"source": "api_manual_entry"},
    )
    return memory


@router.get("/search", response_model=List[MemoryItem])
async def search_user_memories(
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    threshold: Optional[float] = Query(None, ge=0.0, le=1.0),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Performs semantic vector and structured search over the user's memories."""
    return await memory_service.retrieve_memories(
        user_id=current_user.user_id,
        query=query,
        top_k=top_k,
        similarity_threshold=threshold,
    )


@router.patch("/{memory_id}", response_model=MemoryItem)
async def update_user_memory(
    memory_id: int,
    body: MemoryUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Updates an existing memory belonging to the user."""
    updated = await memory_service.update_memory(
        user_id=current_user.user_id,
        memory_id=memory_id,
        update=body,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Memory not found or access denied")
    return updated


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_memory(
    memory_id: int,
    hard_delete: bool = Query(False, description="Whether to permanently remove row"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Deletes or archives a memory record belonging to the user."""
    success = await memory_service.delete_memory(
        user_id=current_user.user_id,
        memory_id=memory_id,
        hard_delete=hard_delete,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found or access denied")
    return None
