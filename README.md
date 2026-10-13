# LangGraph Multi-Tenant AI Chatbot

A production-grade, full-stack AI chatbot platform built with **FastAPI**, **LangGraph**, **Next.js 16 (React 19)**, and **PostgreSQL**.

---

## Key Highlights

- **PostgreSQL-Only Authentication**: Secure Argon2id password hashing, high-entropy cryptographic sessions, HTTP-only session cookies, and Google OAuth 2.0 integration without external SaaS dependencies.
- **Strict Multi-Tenant Isolation**: Row-level thread ownership guards (`403 Forbidden`) protecting user conversation data.
- **Short-Term Memory & Auto-Summarization**: Windowed working context managed by LangGraph with automatic conversation summarization.
- **Tool Ecosystem**: 12 registered tools (Gmail with Human-in-the-Loop approval, YouTube, Amazon search, Stock tickers, SerpAPI, ArXiv, Wikipedia, and Weather).
- **Modern Layered Architecture**: Modular package organization adhering to standard software engineering best practices.

---

## Directory Structure

```
lamit/
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints (auth, threads, chat, history, router)
│   │   ├── core/           # Infrastructure (config, database pool, security & auth)
│   │   ├── graph/          # LangGraph engine, state, nodes, routing, and tools
│   │   ├── schemas/        # Typed Pydantic request/response models
│   │   ├── services/       # Business services (AI conversation title generator)
│   │   └── main.py         # FastAPI application factory & lifespan runner
│   ├── tests/              # Test suites (auth isolation, SSE streaming, audits, E2E)
│   ├── Dockerfile          # Production backend Docker image
│   └── main.py             # Entrypoint shim
├── web/
│   ├── src/
│   │   ├── app/            # Next.js App router
│   │   ├── components/     # Categorized components (auth/, chat/, layout/)
│   │   ├── hooks/          # Custom streaming hook (useChatStream)
│   │   └── lib/            # Types and API client
│   └── package.json
├── docker-compose.yml      # Orchestration for FastAPI, PostgreSQL, and Next.js
└── PRODUCTION_READINESS.md # Full security audit and operations runbook
```

---

## Quickstart

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+

### 2. Environment Setup
Copy the template and fill in your keys:
```bash
cp .env.example .env
```
Ensure `POSTGRES_URI` and `OPENAI_API_KEY` are configured.

### 3. Run Backend
```bash
# Windows
..\venv\Scripts\python.exe -m backend.main

# Linux/macOS
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation is available at `http://127.0.0.1:8000/docs`.

### 4. Run Frontend
```bash
cd web
npm install
npm run dev -- -p 3000
```
Open `http://localhost:3000` in your browser.

### 5. Run Verification Tests
```bash
python -m backend.tests.test_auth_isolation
python -m backend.tests.test_streaming
python -m backend.tests.test_production_readiness
python -m backend.tests.test_final_e2e
```
