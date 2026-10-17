# Production Readiness Engineering Review & Deployment Runbook

## Executive Summary
This document provides a comprehensive architecture audit and operational runbook for the refactored **LangGraph AI Chatbot** application located in `lamit`.

The project adheres to modern software engineering standards:
- **Clean Layered Architecture**: Clear separation of concerns into `core`, `schemas`, `services`, `graph`, `api`, and test suites.
- **Enterprise-Grade Security**: Self-hosted PostgreSQL authentication (Argon2id password hashing, high-entropy cryptographic session tokens, HTTP-only SameSite cookies, Google OAuth 2.0).
- **Multi-Tenant Data Isolation**: Cryptographically enforced row-level data access ensuring users cannot read, mutate, or delete conversations belonging to others (`403 Forbidden`).
- **Human-in-the-Loop (HITL) Guardrails**: Sensitive external actions (e.g. Gmail outbound dispatch) are gated by LangGraph state machine interrupts with user approval/rejection resume workflows.
- **Next.js 16 (React 19) Frontend**: High-performance UI structured into categorized component domains (`auth/`, `chat/`, `layout/`) with barrel exports and TypeScript safety.

---

## 1. Directory Structure Standards

```
lamit/
├── .env                              # Environment configuration (PostgreSQL URI, OpenAI, OAuth)
├── .env.example                      # Configuration template with setup guidelines
├── docker-compose.yml                # Multi-service container orchestration (FastAPI + Next.js + Postgres)
├── PRODUCTION_READINESS.md           # This architecture & operations review
│
├── backend/
│   ├── Dockerfile                    # Production multi-stage Python container
│   ├── main.py                       # Root backward-compatible entrypoint shim
│   ├── auth.py                       # Backward-compatible auth shim
│   ├── schemas.py                    # Backward-compatible schemas shim
│   ├── thread_title.py               # Backward-compatible title service shim
│   ├── chatbot_mcp.py                # Backward-compatible graph engine shim
│   │
│   ├── app/                          # Core Modular Backend Package
│   │   ├── __init__.py               # App package exports
│   │   ├── main.py                   # FastAPI app factory (create_app), lifespan, CORS, error handling
│   │   │
│   │   ├── core/                     # Infrastructure & Core Logic
│   │   │   ├── config.py             # Strongly-typed environment settings
│   │   │   ├── database.py           # Psycopg AsyncConnectionPool & idempotent migrations
│   │   │   └── security.py           # Argon2id hashing, session token gen, auth dependencies, thread isolation
│   │   │
│   │   ├── schemas/                  # Pydantic Request & Response Models
│   │   │   ├── auth.py               # Signup, Login, User, Google token verification schemas
│   │   │   ├── thread.py             # ThreadItem, ThreadCreate, ChatMessageItem, ChatHistory schemas
│   │   │   └── chat.py               # ChatStreamRequest, ChatResumeRequest schemas
│   │   │
│   │   ├── services/                 # Domain Business Services
│   │   │   └── title_service.py      # LLM automated conversation title generation
│   │   │
│   │   ├── graph/                    # LangGraph Engine & Tool Ecosystem
│   │   │   ├── state.py              # ChatState with STM messages and persistent summary
│   │   │   ├── nodes.py              # chat_node (LLM with bound tools) & summarize_node
│   │   │   ├── routing.py            # route_after_chat and summary condition routing
│   │   │   ├── engine.py             # StateGraph definition and AsyncPostgresSaver checkpointer
│   │   │   └── tools/                # Specialized LLM Tools
│   │   │       ├── registry.py       # Centralized 12-tool registry array
│   │   │       ├── gmail_tool.py     # Gmail read/send with HITL approval interrupt
│   │   │       ├── amazon_tool.py    # Product searching
│   │   │       ├── youtube_tool.py   # Video search & transcript analysis
│   │   │       ├── stock_price.py    # Real-time stock quotes
│   │   │       ├── arxiv_search.py   # Academic research paper search
│   │   │       ├── google_scholar.py # Scholarly citations
│   │   │       ├── google_search.py  # SerpAPI web query
│   │   │       ├── duckduckgo_search.py # Privacy web search
│   │   │       ├── wikipedia_search.py  # Encyclopedia lookups
│   │   │       ├── get_weather.py    # Live weather forecasts
│   │   │       └── get_lat_long.py   # Geocoding coordinates
│   │   │
│   │   └── api/                      # REST API Endpoints
│   │       ├── router.py             # Central APIRouter mounting all sub-routes
│   │       ├── auth.py               # /api/auth (signup, login, logout, me, google)
│   │       ├── threads.py            # /api/threads (CRUD, listing, renaming)
│   │       ├── history.py            # /api/threads/{id}/messages (message retrieval)
│   │       └── chat.py               # /api/chat/stream & /api/chat/resume (SSE streaming)
│   │
│   └── tests/                        # Automated Integration Test Suite
│       ├── test_auth_isolation.py    # Tests user signup, login, session cookies, and 403 cross-user guards
│       ├── test_streaming.py         # Tests real-time SSE token streaming and chat_messages persistence
│       ├── test_production_readiness.py # Tests HITL interrupts, security audits, and concurrency
│       └── test_final_e2e.py         # Full end-to-end user journey test
│
└── web/                              # Next.js 16 Web Application
    ├── package.json                  # Dependencies (Lucide React, Tailwind, Next.js)
    ├── next.config.ts                # Next.js configuration
    └── src/
        ├── app/
        │   ├── layout.tsx            # Root layout with fonts and metadata
        │   ├── globals.css           # Modern theme styling and custom scrollbars
        │   └── page.tsx              # Main chat interface and state orchestration
        │
        ├── components/               # Categorized Component Modules
        │   ├── index.ts              # Central barrel export
        │   ├── auth/                 # Authentication Dialogs & Forms
        │   │   ├── AuthModal.tsx     # Email/password + Google Sign-In modal
        │   │   └── index.ts          # Auth module barrel export
        │   ├── chat/                 # Conversation & Message Views
        │   │   ├── ChatContainer.tsx # Message stream viewport and tool call badges
        │   │   ├── MessageItem.tsx   # Individual user/assistant bubble with Markdown support
        │   │   ├── MessageInput.tsx  # Dynamic textarea, send, stop, and interrupt actions
        │   │   ├── EmptyState.tsx    # Welcome cards and suggested prompt starters
        │   │   └── index.ts          # Chat module barrel export
        │   └── layout/               # Shell Layout Components
        │       ├── Sidebar.tsx       # Thread navigation, search, rename, delete, user profile
        │       └── index.ts          # Layout module barrel export
        │
        ├── hooks/
        │   └── useChatStream.ts      # Custom hook managing SSE streaming, tool events, and interrupts
        └── lib/
            ├── api.ts                # Typed API client with credentials include
            └── types.ts              # TypeScript domain types (Thread, Message, User, SSEEvent)
```

---

## 2. Security Architecture & Authorization Boundaries

### Self-Hosted PostgreSQL Authentication (`backend/app/core/security.py`)
- **Zero Third-Party Dependency**: No Supabase or Firebase required; all tables reside strictly in your PostgreSQL cluster.
- **Password Protection**: Industry-standard **Argon2id** (`argon2-cffi`) hashing algorithm with salt generation.
- **Session Tokens**: 256-bit cryptographically secure pseudorandom tokens (`secrets.token_urlsafe(32)`) stored in `user_sessions`.
- **HTTP-Only Cookies**: Automatically set with:
  - `httponly=True` (impervious to XSS credential extraction)
  - `samesite="lax"` (CSRF defense)
  - `secure=True` (in production HTTPS mode)
  - Also accepts standard `Authorization: Bearer <token>` headers for CLI or mobile clients.
- **Google OAuth 2.0 Integration**:
  - `GET /api/auth/google/url`: Constructs Google consent URL requesting email, profile, and OpenID scopes.
  - `GET /api/auth/google/callback`: Exchanges authorization code with Google token endpoint, creates/links user, and issues authenticated session cookie.
  - `POST /api/auth/google/verify`: Accepts Google One-Tap ID tokens and validates integrity.

### Multi-Tenant Conversation Isolation
- **Row-Level Enforcement**: Every thread in `chat_threads` is bound to `user_id TEXT NOT NULL`.
- **Authorization Guard**: The dependency `verify_thread_ownership(conn, thread_id, user_id)` verifies ownership on every access:
  - Attempting to read messages of an unowned thread $\to$ `403 Forbidden`
  - Attempting to stream into an unowned thread $\to$ `403 Forbidden`
  - Attempting to rename an unowned thread $\to$ `403 Forbidden`
  - Attempting to delete an unowned thread $\to$ `403 Forbidden`
- **Thread Enumeration Defense**: `GET /api/threads` filters strictly `WHERE user_id = :user_id`.

---

## 3. Human-in-the-Loop (HITL) Approval Workflows

### Sensitive Outbound Actions (`backend/app/graph/tools/gmail_tool.py`)
- Outbound emails triggered by `send_gmail_message` execute `langgraph.types.interrupt(...)`.
- The graph captures the pending tool call and halts execution, sending an SSE event `interrupt` to the client.
- The UI surfaces an interactive approval prompt displaying the recipient, subject, and message snippet.
- Resumption is processed via `POST /api/chat/resume`:
  - If approved (`true`), email sends and results stream back.
  - If rejected (`false`), the tool safely aborts with an audit cancellation message.

---

## 4. Verification Test Matrix

All test suites have passed with 100% success on the updated modular codebase:

| Test Suite | Execution Command | Result | Scope |
| :--- | :--- | :--- | :--- |
| **Auth & Isolation** | `python -m backend.tests.test_auth_isolation` | **PASSED** | Signup, login, HTTP-only cookie, 401 unauth checks, 403 cross-user isolation, logout |
| **SSE Streaming** | `python -m backend.tests.test_streaming` | **PASSED** | Real-time token streaming, event parsing, PostgreSQL `chat_messages` persistence |
| **Production Readiness** | `python -m backend.tests.test_production_readiness` | **PASSED** | Tool interrupt guards, cross-user read/write/delete rejections, thread cleanup |
| **Final E2E Suite** | `python -m backend.tests.test_final_e2e` | **PASSED** | Health check, user creation, multiple threads, live LLM generation, rename, cleanup |
| **Next.js 16 Web Build** | `npm run build` (in `web/`) | **PASSED** | TypeScript type checking, static page generation, Turbopack bundle verification |

---

## 5. Development & Production Operations

### Running Locally

1. **Backend**:
   ```bash
   cd lamit
   ..\venv\Scripts\python.exe -m backend.main
   ```
   *(Backend serves at `http://127.0.0.1:8000` with Swagger docs at `http://127.0.0.1:8000/docs`)*

2. **Frontend**:
   ```bash
   cd lamit/web
   npm run dev -- -p 3000
   ```
   *(Web app serves at `http://localhost:3000`)*

### Running with Docker Compose

```bash
cd lamit
docker-compose up -d --build
```
This automatically boots PostgreSQL, runs migrations, builds the FastAPI backend, and serves the Next.js web frontend.

---

## 6. Semantic Caching Architecture & Verification

The production semantic caching layer reduces LLM latency and costs by caching semantically equivalent queries using PostgreSQL vector math.

### Key Capabilities
- **PostgreSQL Vector Storage**: Uses vector arrays (`DOUBLE PRECISION[]`) with a native PL/pgSQL `cosine_similarity_array` function for zero external database dependencies.
- **Two-Tier Lookup**:
  1. *O(1) Exact Match*: SHA-256 normalized query hash lookup for sub-millisecond retrieval.
  2. *Cosine Similarity Search*: Vector similarity search returning cached responses when `similarity >= SEMANTIC_CACHE_SIMILARITY_THRESHOLD` (default: `0.88`).
- **Multi-Tenant Isolation**: Queries and cached responses are strictly scoped by `user_id` to prevent cross-user leakage.
- **Tool-Dependent Ineligibility**: Queries executing dynamic, time-sensitive tools (weather, stocks, search) or side-effecting operations (Gmail sending, HITL interrupts) are automatically excluded from the cache.
- **Conversational Memory Sync**: On a cache hit, LangGraph's checkpointer state (`bot.aupdate_state`) is updated with the turn so short-term memory and history summarization remain 100% accurate.
- **Graceful Fallback**: Any embedding provider failure or database timeout gracefully falls back to the live LangGraph chatbot execution without interrupting the user.

### Verification Matrix

| Test Suite | Command | Result | Scope |
| :--- | :--- | :--- | :--- |
| **Semantic Cache Unit & Integration** | `python -u backend/tests/test_semantic_cache.py` | **PASSED** | Cosine similarity math, O(1) exact hash hits, thresholding (0.88), tenant isolation, TTL expiration/invalidation, tool ineligibility, failure fallback, concurrency |
| **Semantic Cache E2E Streaming** | `python -u backend/tests/test_semantic_cache_e2e.py` | **PASSED** | Full FastAPI `/api/chat/stream` SSE streaming with cache hit fast-path, checkpointer synchronization, PostgreSQL `chat_messages` audit, cross-user isolation |

