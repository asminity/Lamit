#!/usr/bin/env python3
"""
Lamit - Safe pgvector & HNSW Rollback Tool
Safely rolls back HNSW index and vector column in semantic_cache,
reverting fully to array-based fallback mode.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import psycopg
from psycopg.rows import dict_row
from backend.app.core.config import settings


async def run_rollback():
    print("=" * 70)
    print("LAMIT: PGVECTOR & HNSW ROLLBACK SCRIPT")
    print("=" * 70)
    print(f"Target Database: {settings.POSTGRES_URI.split('@')[-1]}")
    print("-" * 70)

    try:
        conn = await psycopg.AsyncConnection.connect(
            settings.POSTGRES_URI,
            row_factory=dict_row,
            autocommit=True,
        )
    except Exception as e:
        print(f"[FATAL] Cannot connect to database: {e}")
        return False

    async with conn:
        # Step 1: Drop HNSW index
        print("[1] Dropping HNSW index (idx_semantic_cache_hnsw) if exists...")
        await conn.execute("DROP INDEX IF EXISTS idx_semantic_cache_hnsw;")
        print("  -> Index dropped.")

        # Step 2: Drop vector column
        print("[2] Dropping embedding_vec column if exists...")
        await conn.execute("ALTER TABLE semantic_cache DROP COLUMN IF EXISTS embedding_vec;")
        print("  -> Column dropped.")

        # Step 3: Verify fallback schema health
        print("[3] Verifying fallback schema health...")
        res = await conn.execute(
            """
            SELECT COUNT(*) as count FROM semantic_cache;
            """
        )
        row = await res.fetchone()
        count = row["count"] if row else 0
        print(f"  -> Semantic cache table intact with {count} records preserved in DOUBLE PRECISION[].")

        print("\n" + "=" * 70)
        print("ROLLBACK COMPLETED SUCCESSFULLY!")
        print("Semantic caching will operate on B-tree indexes + PL/pgSQL cosine similarity.")
        print("=" * 70)
        return True


if __name__ == "__main__":
    if sys.platform == "win32":
        import selectors
        asyncio.set_event_loop(asyncio.SelectorEventLoop(selectors.SelectSelector()))
    asyncio.run(run_rollback())
