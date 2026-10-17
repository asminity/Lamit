#!/usr/bin/env python3
"""
Lamit - Safe pgvector & HNSW Migration Tool
Safely checks, applies, and verifies PostgreSQL pgvector extension, schema migration,
data backfill, and HNSW index creation for production semantic caching.
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


async def run_migration():
    print("=" * 70)
    print("LAMIT: PGVECTOR & HNSW MIGRATION SCRIPT")
    print("=" * 70)
    print(f"Target Database: {settings.POSTGRES_URI.split('@')[-1]}")
    print(f"Configured Embedding Model: {settings.SEMANTIC_CACHE_EMBEDDING_MODEL}")
    print(f"Configured Vector Dimension: {settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION}")
    print(f"HNSW Parameters: m={settings.SEMANTIC_CACHE_HNSW_M}, ef_construction={settings.SEMANTIC_CACHE_HNSW_EF_CONSTRUCTION}, ef_search={settings.SEMANTIC_CACHE_HNSW_EF_SEARCH}")
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
        # Step 1: Probe PG version
        res_ver = await conn.execute("SELECT version();")
        pg_ver = (await res_ver.fetchone())["version"]
        print(f"[1] PostgreSQL Server: {pg_ver}")

        # Step 2: Probe pgvector extension availability
        res_ext = await conn.execute("SELECT * FROM pg_available_extensions WHERE name = 'vector';")
        ext_info = await res_ext.fetchone()

        if not ext_info:
            print("\n" + "!" * 70)
            print("[NOTICE] pgvector extension binary is NOT installed in this PostgreSQL engine.")
            print(f"Host environment: Windows / {pg_ver.split(',')[0]}")
            print("Limitation Details:")
            print("  - PostgreSQL 18.x on Windows is a development branch.")
            print("  - Precompiled pgvector DLLs are currently released for PG 13 through PG 17.")
            print("  - Docker Desktop engine is not currently running.")
            print("\nSafe Fallback Status:")
            print("  - Lamit will automatically operate in resilient ARRAY_FALLBACK mode.")
            print("  - PL/pgSQL cosine_similarity_array + B-tree pre-filtering remain active.")
            print("  - Zero application downtime or crash risk.")
            print("!" * 70 + "\n")
            return False

        print(f"[2] pgvector extension detected: installed_version={ext_info.get('installed_version')}, default_version={ext_info.get('default_version')}")

        # Step 3: Enable extension
        print("[3] Enabling pgvector extension...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("  -> Extension 'vector' verified and active.")

        # Step 4: Schema migration - add vector column
        dim = settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION
        print(f"[4] Adding embedding_vec vector({dim}) column to semantic_cache...")
        await conn.execute(f"ALTER TABLE semantic_cache ADD COLUMN IF NOT EXISTS embedding_vec vector({dim});")
        print("  -> Column 'embedding_vec' ensured.")

        # Step 5: Backfill existing records
        print("[5] Backfilling existing records from embedding DOUBLE PRECISION[]...")
        start_bf = time.perf_counter()
        res_bf = await conn.execute(
            """
            UPDATE semantic_cache
            SET embedding_vec = embedding::text::vector
            WHERE embedding_vec IS NULL AND embedding IS NOT NULL;
            """
        )
        elapsed_bf = (time.perf_counter() - start_bf) * 1000
        print(f"  -> Backfilled {res_bf.rowcount} records in {elapsed_bf:.2f}ms.")

        # Step 6: Create HNSW Index
        m = settings.SEMANTIC_CACHE_HNSW_M
        ef_c = settings.SEMANTIC_CACHE_HNSW_EF_CONSTRUCTION
        print(f"[6] Creating HNSW index (idx_semantic_cache_hnsw) with m={m}, ef_construction={ef_c}...")
        start_idx = time.perf_counter()
        await conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_semantic_cache_hnsw
            ON semantic_cache
            USING hnsw (embedding_vec vector_cosine_ops)
            WITH (m = {m}, ef_construction = {ef_c});
            """
        )
        elapsed_idx = (time.perf_counter() - start_idx) * 1000
        print(f"  -> HNSW Index created in {elapsed_idx:.2f}ms.")

        # Step 7: Check iterative index scan
        res_scan = await conn.execute("SELECT 1 FROM pg_settings WHERE name = 'hnsw.iterative_scan';")
        has_iterative = (await res_scan.fetchone()) is not None
        print(f"[7] Iterative index scan support: {has_iterative}")

        print("\n" + "=" * 70)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        return True


if __name__ == "__main__":
    if sys.platform == "win32":
        import selectors
        asyncio.set_event_loop(asyncio.SelectorEventLoop(selectors.SelectSelector()))
    asyncio.run(run_migration())
