import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from backend.app.core.config import settings
from backend.app.core.database import (
    get_db_pool,
    is_pgvector_available,
)
from backend.app.schemas.memory import (
    MemoryType,
    MemoryItem,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    ExtractedMemory,
)

logger = logging.getLogger("memory_service")


class MemoryService:
    def __init__(
        self,
        embeddings_client: Optional[Any] = None,
        extraction_llm: Optional[Any] = None,
        enabled: Optional[bool] = None,
        similarity_threshold: Optional[float] = None,
        top_k: Optional[int] = None,
        importance_threshold: Optional[float] = None,
    ):
        self.enabled = settings.LTM_ENABLED if enabled is None else enabled
        self.similarity_threshold = (
            settings.LTM_SIMILARITY_THRESHOLD
            if similarity_threshold is None
            else similarity_threshold
        )
        self.top_k = settings.LTM_TOP_K if top_k is None else top_k
        self.importance_threshold = (
            settings.LTM_IMPORTANCE_THRESHOLD
            if importance_threshold is None
            else importance_threshold
        )
        self._embeddings_client = embeddings_client
        self._extraction_llm = extraction_llm

    def get_embeddings_client(self):
        if self._embeddings_client is None:
            self._embeddings_client = OpenAIEmbeddings(
                model=settings.SEMANTIC_CACHE_EMBEDDING_MODEL,
                api_key=settings.OPENAI_API_KEY,
            )
        return self._embeddings_client

    def get_extraction_llm(self):
        if self._extraction_llm is None:
            self._extraction_llm = ChatOpenAI(
                model=settings.LTM_EXTRACTION_MODEL,
                temperature=0.0,
            )
        return self._extraction_llm

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generates embedding vector for a piece of text with graceful error handling."""
        try:
            client = self.get_embeddings_client()
            return await client.aembed_query(text.strip())
        except Exception as e:
            logger.warning(f"Failed to generate embedding for memory: {e}")
            return None

    # --------------------------------------------------------------------------
    # 1. Memory CRUD Operations (Strict Multi-Tenant Isolation)
    # --------------------------------------------------------------------------

    async def add_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        structured_data: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        confidence: float = 1.0,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> MemoryItem:
        """
        Stores a memory with deduplication and supersession detection.
        Strictly scopes all queries and writes to user_id.
        """
        pool = await get_db_pool()
        content = content.strip()
        structured_data = structured_data or {}
        provenance = provenance or {}

        # 1. Deduplication / Supersession check
        supersedes_id = None
        async with pool.connection() as conn:
            # Check existing active memories for this user
            res = await conn.execute(
                """
                SELECT id, content, structured_data, importance, confidence
                FROM user_memories
                WHERE user_id = %s AND is_active = TRUE AND memory_type = %s
                """,
                (user_id, memory_type),
            )
            existing_memories = await res.fetchall()

            new_key = structured_data.get("key")
            for em in existing_memories:
                em_content = em["content"].strip().lower()
                em_struct = em["structured_data"] or {}
                em_key = em_struct.get("key")

                # Exact duplicate content -> boost confidence & touch timestamp
                if em_content == content.lower():
                    updated_conf = max(em["confidence"], confidence)
                    await conn.execute(
                        """
                        UPDATE user_memories
                        SET confidence = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s AND user_id = %s
                        """,
                        (updated_conf, em["id"], user_id),
                    )
                    logger.info(f"Deduplicated existing memory id={em['id']} for user={user_id}")
                    return MemoryItem(
                        id=em["id"],
                        user_id=user_id,
                        memory_type=memory_type,
                        content=em["content"],
                        structured_data=em_struct,
                        importance=em["importance"],
                        confidence=updated_conf,
                        provenance=provenance,
                        is_active=True,
                    )

                # Key conflict (e.g. key="preferred_framework" updated from React to Vue)
                if new_key and em_key and new_key.lower() == em_key.lower():
                    supersedes_id = em["id"]
                    break

        # 2. Generate embedding
        embedding = await self.get_embedding(content)

        # 3. Persist new memory
        async with pool.connection() as conn:
            pgv = is_pgvector_available()
            if pgv and embedding:
                emb_str = "[" + ",".join(str(x) for x in embedding) + "]"
                res = await conn.execute(
                    """
                    INSERT INTO user_memories (
                        user_id, memory_type, content, structured_data,
                        importance, confidence, provenance, embedding, embedding_vec
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    RETURNING id, created_at, updated_at;
                    """,
                    (
                        user_id,
                        memory_type,
                        content,
                        json.dumps(structured_data),
                        importance,
                        confidence,
                        json.dumps(provenance),
                        embedding,
                        emb_str,
                    ),
                )
            else:
                res = await conn.execute(
                    """
                    INSERT INTO user_memories (
                        user_id, memory_type, content, structured_data,
                        importance, confidence, provenance, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, created_at, updated_at;
                    """,
                    (
                        user_id,
                        memory_type,
                        content,
                        json.dumps(structured_data),
                        importance,
                        confidence,
                        json.dumps(provenance),
                        embedding,
                    ),
                )
            row = await res.fetchone()
            new_id = row["id"]

            # Supersede old conflicting memory if detected
            if supersedes_id is not None:
                await conn.execute(
                    """
                    UPDATE user_memories
                    SET is_active = FALSE, superseded_by = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND user_id = %s
                    """,
                    (new_id, supersedes_id, user_id),
                )
                logger.info(f"Superseded memory id={supersedes_id} with new memory id={new_id} for user={user_id}")

        logger.info(f"Stored LTM memory id={new_id} type={memory_type} for user={user_id}")
        return MemoryItem(
            id=new_id,
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            structured_data=structured_data,
            importance=importance,
            confidence=confidence,
            provenance=provenance,
            is_active=True,
            superseded_by=None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_memories(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        is_active: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[MemoryItem]:
        """Lists memories strictly filtered by authenticated user_id."""
        pool = await get_db_pool()
        query = """
            SELECT id, user_id, memory_type, content, structured_data,
                   importance, confidence, provenance, is_active, superseded_by,
                   created_at, updated_at
            FROM user_memories
            WHERE user_id = %s AND is_active = %s
        """
        params: List[Any] = [user_id, is_active]

        if memory_type:
            query += " AND memory_type = %s"
            params.append(memory_type)

        query += " ORDER BY updated_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        async with pool.connection() as conn:
            res = await conn.execute(query, tuple(params))
            rows = await res.fetchall()

        return [
            MemoryItem(
                id=r["id"],
                user_id=r["user_id"],
                memory_type=r["memory_type"],
                content=r["content"],
                structured_data=r["structured_data"] or {},
                importance=r["importance"],
                confidence=r["confidence"],
                provenance=r["provenance"] or {},
                is_active=r["is_active"],
                superseded_by=r["superseded_by"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def delete_memory(self, user_id: str, memory_id: int, hard_delete: bool = False) -> bool:
        """Deletes a memory, either soft (is_active=False) or hard."""
        pool = await get_db_pool()
        async with pool.connection() as conn:
            if hard_delete:
                res = await conn.execute(
                    "DELETE FROM user_memories WHERE id = %s AND user_id = %s RETURNING id",
                    (memory_id, user_id),
                )
            else:
                res = await conn.execute(
                    """
                    UPDATE user_memories
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                    """,
                    (memory_id, user_id),
                )
            row = await res.fetchone()
            return row is not None

    async def update_memory(
        self,
        user_id: str,
        memory_id: int,
        update: MemoryUpdateRequest,
    ) -> Optional[MemoryItem]:
        """Updates an existing memory record strictly owned by user_id."""
        pool = await get_db_pool()
        async with pool.connection() as conn:
            res = await conn.execute(
                "SELECT * FROM user_memories WHERE id = %s AND user_id = %s",
                (memory_id, user_id),
            )
            existing = await res.fetchone()
            if not existing:
                return None

            new_content = update.content if update.content is not None else existing["content"]
            new_struct = update.structured_data if update.structured_data is not None else existing["structured_data"]
            new_imp = update.importance if update.importance is not None else existing["importance"]
            new_conf = update.confidence if update.confidence is not None else existing["confidence"]
            new_active = update.is_active if update.is_active is not None else existing["is_active"]

            # If content changed, re-embed
            new_embedding = existing["embedding"]
            if update.content is not None and update.content != existing["content"]:
                new_embedding = await self.get_embedding(new_content)

            pgv = is_pgvector_available()
            if pgv and new_embedding:
                emb_str = "[" + ",".join(str(x) for x in new_embedding) + "]"
                res_upd = await conn.execute(
                    """
                    UPDATE user_memories
                    SET content = %s, structured_data = %s, importance = %s,
                        confidence = %s, is_active = %s, embedding = %s,
                        embedding_vec = %s::vector, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND user_id = %s
                    RETURNING *
                    """,
                    (
                        new_content,
                        json.dumps(new_struct),
                        new_imp,
                        new_conf,
                        new_active,
                        new_embedding,
                        emb_str,
                        memory_id,
                        user_id,
                    ),
                )
            else:
                res_upd = await conn.execute(
                    """
                    UPDATE user_memories
                    SET content = %s, structured_data = %s, importance = %s,
                        confidence = %s, is_active = %s, embedding = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND user_id = %s
                    RETURNING *
                    """,
                    (
                        new_content,
                        json.dumps(new_struct),
                        new_imp,
                        new_conf,
                        new_active,
                        new_embedding,
                        memory_id,
                        user_id,
                    ),
                )
            row = await res_upd.fetchone()

        return MemoryItem(
            id=row["id"],
            user_id=row["user_id"],
            memory_type=row["memory_type"],
            content=row["content"],
            structured_data=row["structured_data"] or {},
            importance=row["importance"],
            confidence=row["confidence"],
            provenance=row["provenance"] or {},
            is_active=row["is_active"],
            superseded_by=row["superseded_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --------------------------------------------------------------------------
    # 2. Retrieval: Structured Facts & pgvector / Cosine Vector Search
    # --------------------------------------------------------------------------

    async def retrieve_memories(
        self,
        user_id: str,
        query: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> List[MemoryItem]:
        """
        Hybrid retrieval:
        1. Always retrieves active core user profile & preferences (via indexed SQL).
        2. Retrieves top-K semantically relevant memories matching the query using vector similarity.
        3. Strictly scoped to user_id (never leaks across tenants).
        """
        if not self.enabled or not user_id:
            return []

        pool = await get_db_pool()
        k = top_k or self.top_k
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self.similarity_threshold
        )

        results: List[MemoryItem] = []
        seen_ids = set()

        # Step 1: Indexed SQL for User Profile and Preferences
        async with pool.connection() as conn:
            res_profile = await conn.execute(
                """
                SELECT id, user_id, memory_type, content, structured_data,
                       importance, confidence, provenance, is_active, superseded_by,
                       created_at, updated_at
                FROM user_memories
                WHERE user_id = %s AND is_active = TRUE
                  AND memory_type IN ('profile', 'preference')
                ORDER BY importance DESC, updated_at DESC
                LIMIT 6
                """,
                (user_id,),
            )
            profile_rows = await res_profile.fetchall()
            for r in profile_rows:
                seen_ids.add(r["id"])
                results.append(
                    MemoryItem(
                        id=r["id"],
                        user_id=r["user_id"],
                        memory_type=r["memory_type"],
                        content=r["content"],
                        structured_data=r["structured_data"] or {},
                        importance=r["importance"],
                        confidence=r["confidence"],
                        provenance=r["provenance"] or {},
                        is_active=r["is_active"],
                        superseded_by=r["superseded_by"],
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                        similarity_score=1.0,
                    )
                )

        # Step 2: Vector search for episodic & semantic facts
        query_embedding = await self.get_embedding(query)
        if query_embedding:
            async with pool.connection() as conn:
                pgv = is_pgvector_available()
                if pgv:
                    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
                    res_vec = await conn.execute(
                        """
                        SELECT id, user_id, memory_type, content, structured_data,
                               importance, confidence, provenance, is_active, superseded_by,
                               created_at, updated_at,
                               (1.0 - (embedding_vec <=> %s::vector)) AS sim_score
                        FROM user_memories
                        WHERE user_id = %s AND is_active = TRUE AND embedding_vec IS NOT NULL
                          AND (1.0 - (embedding_vec <=> %s::vector)) >= %s
                        ORDER BY sim_score DESC
                        LIMIT %s
                        """,
                        (emb_str, user_id, emb_str, threshold, k),
                    )
                else:
                    res_vec = await conn.execute(
                        """
                        SELECT id, user_id, memory_type, content, structured_data,
                               importance, confidence, provenance, is_active, superseded_by,
                               created_at, updated_at,
                               cosine_similarity_array(embedding, %s) AS sim_score
                        FROM user_memories
                        WHERE user_id = %s AND is_active = TRUE AND embedding IS NOT NULL
                          AND cosine_similarity_array(embedding, %s) >= %s
                        ORDER BY sim_score DESC
                        LIMIT %s
                        """,
                        (query_embedding, user_id, query_embedding, threshold, k),
                    )
                vec_rows = await res_vec.fetchall()
                for r in vec_rows:
                    if r["id"] not in seen_ids:
                        seen_ids.add(r["id"])
                        results.append(
                            MemoryItem(
                                id=r["id"],
                                user_id=r["user_id"],
                                memory_type=r["memory_type"],
                                content=r["content"],
                                structured_data=r["structured_data"] or {},
                                importance=r["importance"],
                                confidence=r["confidence"],
                                provenance=r["provenance"] or {},
                                is_active=r["is_active"],
                                superseded_by=r["superseded_by"],
                                created_at=r["created_at"],
                                updated_at=r["updated_at"],
                                similarity_score=float(r["sim_score"]),
                            )
                        )

        return results

    def format_memories_for_prompt(self, memories: List[MemoryItem]) -> str:
        """Formats retrieved memories into structured prompt context."""
        if not memories:
            return ""

        profiles = [m for m in memories if m.memory_type == MemoryType.PROFILE.value]
        preferences = [m for m in memories if m.memory_type == MemoryType.PREFERENCE.value]
        facts = [
            m for m in memories
            if m.memory_type in (
                MemoryType.SEMANTIC_FACT.value,
                MemoryType.PROJECT_KNOWLEDGE.value,
                MemoryType.EPISODIC.value,
            )
        ]

        blocks = []
        if profiles:
            blocks.append("User Profile:")
            for p in profiles:
                blocks.append(f"- {p.content}")
        if preferences:
            blocks.append("User Preferences:")
            for pref in preferences:
                blocks.append(f"- {pref.content}")
        if facts:
            blocks.append("Relevant Knowledge & Past Context:")
            for f in facts:
                blocks.append(f"- {f.content}")

        return "\n".join(blocks)

    # --------------------------------------------------------------------------
    # 3. Memory Extraction & Lifecycle Management
    # --------------------------------------------------------------------------

    def is_worth_extracting(self, user_message: str) -> bool:
        """Heuristic filter to reject trivial chatter without invoking LLM."""
        text = user_message.strip().lower()
        if len(text) < 6:
            return False
        trivial_phrases = {
            "hi", "hello", "hey", "good morning", "good evening", "thanks",
            "thank you", "ok", "okay", "yes", "no", "bye", "goodbye", "help",
            "what can you do", "ping", "test",
        }
        if text in trivial_phrases:
            return False
        return True

    async def extract_and_store_memories_async(
        self,
        user_id: str,
        thread_id: str,
        user_message: str,
        assistant_message: str,
    ):
        """
        Asynchronously extracts salient user facts, preferences, and knowledge.
        Non-blocking, robust against extraction failure.
        """
        if not self.enabled or not user_id:
            return

        if not self.is_worth_extracting(user_message):
            return

        try:
            llm = self.get_extraction_llm()
            extraction_prompt = f"""You are an autonomous long-term memory extraction agent.
Analyze the following user-assistant conversation turn. Extract durable, salient facts, preferences, profile information, or project knowledge about the user.

Rules:
1. DO NOT extract transient conversational pleasantries, momentary greetings, or ephemeral answers.
2. DO NOT extract information about general public topics unless it reflects the user's specific project or personal preference.
3. Classify each memory as: 'profile', 'preference', 'episodic', 'semantic_fact', or 'project_knowledge'.
4. Assign an importance score (0.0 to 1.0) and confidence score (0.0 to 1.0).
5. Extract a structured_data dictionary (e.g. key, value, subject, predicate, object).
6. If the user is updating an earlier preference (e.g., changing their preferred library from React to Vue), specify 'supersedes_key'.

Respond ONLY with valid JSON conforming to this schema:
{{
  "memories": [
    {{
      "memory_type": "preference",
      "content": "User prefers TypeScript over JavaScript for all frontend code.",
      "structured_data": {{"key": "frontend_language", "value": "TypeScript"}},
      "importance": 0.8,
      "confidence": 1.0,
      "supersedes_key": "frontend_language"
    }}
  ]
}}
If no durable memories are present, return {{"memories": []}}.

Conversation Turn:
User: {user_message}
Assistant: {assistant_message}
"""
            response = await llm.ainvoke([HumanMessage(content=extraction_prompt)])
            raw_text = response.content if isinstance(response.content, str) else str(response.content)

            # Clean JSON markdown if wrapped in ```json ... ```
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            memories_data = parsed.get("memories", [])

            for item in memories_data:
                content = item.get("content", "").strip()
                if not content:
                    continue
                importance = float(item.get("importance", 0.5))
                if importance < self.importance_threshold:
                    continue

                memory_type = item.get("memory_type", "semantic_fact")
                if memory_type not in [e.value for e in MemoryType]:
                    memory_type = "semantic_fact"

                structured_data = item.get("structured_data", {})
                confidence = float(item.get("confidence", 1.0))
                provenance = {
                    "thread_id": thread_id,
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "source": "chat_extraction",
                }

                await self.add_memory(
                    user_id=user_id,
                    memory_type=memory_type,
                    content=content,
                    structured_data=structured_data,
                    importance=importance,
                    confidence=confidence,
                    provenance=provenance,
                )

        except Exception as e:
            logger.warning(f"Asynchronous memory extraction encountered an error: {e}")


# Global singleton service instance
memory_service = MemoryService()
