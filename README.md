# DataPilot 🚀

> **AI-Powered Data Intelligence Platform** — Transform natural-language business requirements into clean, structured, source-backed datasets with autonomous collection workflows.

---

## 🏛️ Monorepo Architecture (Phase 1)

```
DataPilot/
├── apps/
│   ├── web/               # Next.js 14 + TypeScript + Tailwind CSS Frontend
│   └── server/            # FastAPI + Python Async Backend
├── packages/
│   └── shared/            # Shared TypeScript interfaces and configuration constants
├── docker-compose.yml     # PostgreSQL 16 & Redis 7 Container Services
├── .env.example           # Universal Environment Configuration Template
├── .gitignore             # Git ignore rules for Python, Node, Next.js, and DB files
└── package.json           # Monorepo Workspace Configuration
```

---

## 🛠️ Technology Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS | Sleek dark dashboard UI, responsive navigation, API health monitor |
| **Backend** | FastAPI, Python 3.10+, Uvicorn | High-performance async REST API with modular architecture |
| **Database** | PostgreSQL 16 + SQLAlchemy (asyncpg) | Relational persistence with async connection pool |
| **Cache / Queue** | Redis 7 + `redis-py` (asyncio) | High-speed cache and foundation for worker queues |
| **Container** | Docker & Docker Compose | Containerized local dependencies |

---

## ⚡ Quick Start

### 1. Clone & Setup Environment

```bash
# Copy the environment file
cp .env.example .env
```

### 2. Launch Infrastructure (PostgreSQL + Redis)

```bash
docker-compose up -d
```

### 3. Start Backend Server (FastAPI)

```bash
# In a new terminal
cd apps/server

# (Optional) Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server on port 8000 with hot-reload
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **API Overview:** [http://localhost:8000/api/v1/](http://localhost:8000/api/v1/)

### 4. Start Frontend Application (Next.js)

```bash
# From the repository root
npm install
npm run dev:web
```

- **Web Dashboard:** [http://localhost:3000](http://localhost:3000)

---

## 📡 API Endpoints (Phase 1)

### `GET /api/v1/health`
Returns system status and connection health for PostgreSQL and Redis.
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-09-25T15:10:00Z",
  "services": {
    "database": "connected",
    "redis": "connected"
  }
}
```

### `GET /api/v1/`
Returns platform metadata and OpenAPI discoverable links.
```json
{
  "name": "DataPilot",
  "version": "0.1.0",
  "description": "DataPilot - AI-Powered Data Intelligence Platform API",
  "status": "operational",
  "docs_url": "/docs",
  "health_url": "/api/v1/health",
  "api_v1_prefix": "/api/v1",
  "endpoints": {
    "health": "/api/v1/health",
    "docs": "/docs",
    "redoc": "/redoc",
    "openapi": "/openapi.json"
  }
}
```

---

## 🧭 Roadmap

- [x] **Phase 1: Foundation (Current)**
  - Clean scalable monorepo structure
  - FastAPI modular backend with async DB/Redis setup
  - Next.js dark dashboard UI with active routing and health monitoring
  - Docker Compose foundation for PostgreSQL and Redis
- [ ] **Phase 2: AI Agents & Collection Engine**
  - Natural language prompt parsing with LLMs
  - Dynamic scraping & API collector workers
  - Data validation, cleansing, and deduplication pipeline
  - Structured dataset exploration & export (CSV/JSON/Parquet)
