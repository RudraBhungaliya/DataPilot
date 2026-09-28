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

## ⚙️ Phase 3 — Workflow Engine

The **Workflow Engine** translates structured business requirements produced by Phase 2 into a deterministic, validated Directed Acyclic Graph (DAG) execution plan. It coordinates step execution, enforces dependencies, tracks state, and passes outputs across pipeline phases.

### 🔄 Execution Flow Architecture

```
Requirement (Phase 2)
        ↓
Workflow Planning (Deterministic Rules)
        ↓
Workflow Validation (Kahn's Topological Sort & Cycle Detection)
        ↓
Workflow Execution Engine (DAG Dependency Orchestrator)
        ↓
Step Executors (Phase 3 Mock Registry → Phase 4 Real Scrapers)
```

1. **Requirement Understanding**: Decomposes natural language requests into structured entities, locations, constraints, and schemas.
2. **Workflow Planning**: Deterministically builds the necessary steps (`DISCOVER_SOURCES`, `COLLECT_DATA`, `EXTRACT_DATA`, `NORMALIZE_DATA`, `VALIDATE_DATA`, `DEDUPLICATE_DATA`, `BUILD_DATASET`, and conditional `EXPORT_DATA`) without requiring LLM inference.
3. **Workflow Validation**: Uses topological sorting to guarantee step uniqueness, reference integrity, acyclic dependencies, and executable ordering.
4. **Workflow Execution**: Executes steps in dependency order, transitioning states (`PENDING` → `RUNNING` → `COMPLETED` / `FAILED`), capturing errors, and skipping downstream steps upon upstream failure.
5. **Step Executors**: Standardized `BaseStepExecutor` abstraction. In Phase 3, all steps run with `MockStepExecutor` generating clearly marked placeholder outputs (`is_mock: True`). External scrapers and workers activate in Phase 4.

---

### 📋 Example Workflow Definition JSON

```json
{
  "workflow_id": "9f7b6b10-6c9c-4f70-b74d-9658e388d752",
  "name": "Job Posting Intelligence Collection",
  "description": "Find software engineering internships in India posted within the last 7 days.",
  "status": "PLANNED",
  "input_requirement": {
    "objective": "Find software engineering internships in India",
    "entity": "job_posting",
    "location": { "country": "India" },
    "time_constraint": { "type": "posted_within", "value": 7, "unit": "days" },
    "required_fields": ["company_name", "role", "location", "salary", "application_url"],
    "filters": [],
    "source_preferences": ["LinkedIn"],
    "output_format": "table"
  },
  "steps": [
    {
      "id": "step_1",
      "name": "Discover Sources",
      "type": "DISCOVER_SOURCES",
      "description": "Identify and rank high-confidence sources and platforms for job_posting entities.",
      "order": 1,
      "depends_on": [],
      "config": { "entity": "job_posting", "source_preferences": ["LinkedIn"] },
      "status": "PENDING"
    },
    {
      "id": "step_2",
      "name": "Collect Data",
      "type": "COLLECT_DATA",
      "description": "Gather raw records and content payloads from discovered sources.",
      "order": 2,
      "depends_on": ["step_1"],
      "config": { "entity": "job_posting" },
      "status": "PENDING"
    },
    {
      "id": "step_3",
      "name": "Extract Data",
      "type": "EXTRACT_DATA",
      "description": "Parse structured attributes (company_name, role, location, salary) from raw payloads.",
      "order": 3,
      "depends_on": ["step_2"],
      "config": { "entity": "job_posting", "required_fields": ["company_name", "role", "location", "salary", "application_url"] },
      "status": "PENDING"
    },
    {
      "id": "step_4",
      "name": "Normalize Data",
      "type": "NORMALIZE_DATA",
      "description": "Cleanse text, coerce schema types, and standardize date and location formats.",
      "order": 4,
      "depends_on": ["step_3"],
      "config": { "standardize_dates": true, "standardize_locations": true },
      "status": "PENDING"
    },
    {
      "id": "step_5",
      "name": "Validate Data",
      "type": "VALIDATE_DATA",
      "description": "Verify records against schema constraints and 0 filter conditions.",
      "order": 5,
      "depends_on": ["step_4"],
      "config": { "drop_invalid": true },
      "status": "PENDING"
    },
    {
      "id": "step_6",
      "name": "Deduplicate Data",
      "type": "DEDUPLICATE_DATA",
      "description": "Remove redundant records matching duplicate keys: application_url, company_name, role.",
      "order": 6,
      "depends_on": ["step_5"],
      "config": { "deduplication_keys": ["application_url", "company_name", "role"] },
      "status": "PENDING"
    },
    {
      "id": "step_7",
      "name": "Build Dataset",
      "type": "BUILD_DATASET",
      "description": "Compile validated and deduplicated records into a structured dataset.",
      "order": 7,
      "depends_on": ["step_6"],
      "config": { "entity": "job_posting", "output_format": "table" },
      "status": "PENDING"
    }
  ]
}
```

---

## 📡 API Endpoints

### Phase 2: AI Requirement Understanding
- `POST /api/v1/workflows/parse`: Analyzes natural language data requirement prompts with AI and returns a structured specification.

### Phase 3: Workflow Planning & Execution Engine
- `POST /api/v1/workflows/plan`: Generates a validated DAG workflow definition from a structured requirement.
- `POST /api/v1/workflows/{workflow_id}/execute`: Executes a planned workflow through its topological DAG using Phase 3 mock executors.
- `GET /api/v1/workflows/{workflow_id}`: Retrieves workflow definition, current status, execution metadata, and error details.
- `GET /api/v1/workflows/{workflow_id}/steps`: Retrieves step-by-step progress, individual step outputs, and statuses.

### Persistence & System
- `POST /api/v1/workflows`: Confirms or saves a workflow specification.
- `GET /api/v1/workflows`: Lists recent workflow specifications.
- `GET /api/v1/health`: Connection status for PostgreSQL and Redis.
- `GET /api/v1/`: System metadata and discoverable endpoints.

---

## 🧭 Roadmap

- [x] **Phase 1: Foundation**
  - Clean scalable monorepo structure
  - FastAPI modular backend with async DB/Redis setup
  - Next.js dark dashboard UI with active routing and health monitoring
  - Docker Compose foundation for PostgreSQL and Redis
- [x] **Phase 2: AI Requirement Understanding**
  - Natural language prompt parsing with Gemini / AI Provider abstraction
  - Strict Pydantic models for entity, geographic constraints, time boundaries, filters, and schema fields
  - Interactive UI with preset templates and real-time requirement breakdown
- [x] **Phase 3: Workflow Engine**
  - Deterministic DAG workflow planner with conditional step generation
  - Cycle detection & topological dependency validation
  - Dependency-based workflow execution engine
  - Extensible step executor registry with Phase 3 mock executors
  - Interactive visual timeline with live polling and mock output inspection
- [x] **Phase 4: Source Collection Engine**
  - Autonomous source discovery and registry with domain normalization
  - Deterministic source router: API, HTTP, Browser, and Zyte adapter
  - Strict CAPTCHA / Anti-bot policy: zero bypass, Zyte fallback when configured, automatic pivot to alternative sources on failure
  - Raw document store (HTML, JSON, XML, text) preserving provenance and content integrity
  - Full per-domain sliding rate limiter, exponential backoff retries, and canonical URL caching
  - Workflow Engine integration replacing mocks for `DISCOVER_SOURCES` and `COLLECT_DATA`
- [x] **Phase 5: Data Intelligence Pipeline**
  - LLM-first extraction with a deterministic JSON fast-path, full provenance per record
  - Normalization, scored (lenient/strict) validation, composite-key deduplication
  - Dataset compilation with field coverage, CSV/JSON/JSONL export
  - Real executors replacing the mocks for `EXTRACT/NORMALIZE/VALIDATE/DEDUPLICATE/BUILD_DATASET/EXPORT_DATA`
- [x] **Phase 6: Dataset & Evidence Platform**
  - Dataset search, filter, sort and pagination; versioning with `is_latest`
  - Per-record evidence/lineage (record → raw document → registered source) with verification status
  - Datasets explorer UI, workflow & background-task history, CSV/JSON/JSONL export
- [x] **Phase 7: Production & Intelligence**
  - API-key authentication (hashed keys, X-API-Key), per-client Redis rate limiting
  - Background job queue + worker, execute-async endpoints, job monitoring
  - Prometheus `/metrics`, request timing, slow-request logging
  - Configurable robots.txt enforcement, SSRF guardrails, health/readiness

---

## 🚀 Phase 6 & 7 — API Reference

### Datasets (Phase 6)
- `GET /api/v1/datasets?workflow_id=&latest_only=`: list datasets (with version).
- `GET /api/v1/datasets/{id}`: dataset metadata + field coverage.
- `GET /api/v1/datasets/{id}/records?q=&field=&value=&sort=&order=&limit=&offset=`: search/filter/sort/page.
- `GET /api/v1/datasets/{id}/records/{record_id}/evidence`: record provenance chain.
- `GET /api/v1/datasets/{id}/export/{csv|json|jsonl}`: export.

### Operations (Phase 7)
- `POST /api/v1/auth/keys` · `GET /api/v1/auth/keys` · `DELETE /api/v1/auth/keys/{id}`: API keys.
- `POST /api/v1/workflows/{id}/execute-async` · `POST /api/v1/collection/jobs/{id}/execute-async`: queue jobs (202).
- `GET /api/v1/jobs` · `GET /api/v1/jobs/{id}` · `GET /api/v1/jobs/stats`: monitor jobs/queue.
- `GET /metrics`: Prometheus metrics.

### Production configuration
```env
AUTH_ENABLED=True
BOOTSTRAP_API_KEY=<first-run admin key>
RATE_LIMIT_PER_MINUTE=120
RUN_EMBEDDED_WORKER=True        # or False to run a dedicated worker
METRICS_ENABLED=True
DATAPILOT_ROBOTS_ENFORCED=True
```

---

## 🌐 Phase 4 — Source Collection Engine

The **Source Collection Engine** sits between the **Workflow Planner** (Phase 3) and the downstream **Extraction Engine** (Phase 5). It is strictly responsible for discovering where to obtain data, navigating external sources, handling access constraints, and saving immutable raw documents.

> **Strict Boundary Notice:** The Collection Engine preserves raw HTML, JSON, XML, and text payloads verbatim. It does **NOT** perform final entity extraction, normalization, deduplication, or dataset building. Those are downstream responsibilities.

```
Workflow Planner
       │ CollectionRequest
       ▼
┌────────────────────────┐
│   COLLECTION ENGINE    │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│    SOURCE DISCOVERY    │ ── Registry, Direct URLs, Search Provider
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│     SOURCE ROUTER      │ ── Deterministic routing
└──────────┬─────────────┘
           │
    ┌──────┴──────┬──────────────┬─────────────┐
    ▼             ▼              ▼             ▼
   API           HTTP         Browser         Zyte
Collector     Collector      Collector       Adapter
    │             │              │             │
    └──────┬──────┴──────────────┴─────────────┘
           ▼
┌────────────────────────┐
│   COLLECTION MANAGER   │ ── Retries, Rate Limits, Pagination, Caching
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│   RAW DOCUMENT STORE   │ ── Verbatim HTML, JSON, XML, Text + SHA-256
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│   COLLECTION RESULT    │ ── Document references & audit statistics
└────────────────────────┘
```

---

### 🛡️ Access Policy & Anti-Bot Fallback Flow

DataPilot enforces strict ethical and technical access boundaries:
1. **Zero CAPTCHA Bypass**: The engine **NEVER** solves, bypasses, or evades CAPTCHAs or Cloudflare turnstile barriers.
2. **Zyte Adapter Fallback**: When an anti-bot challenge is detected, if `ZYTE_API_KEY` is configured and Zyte access is permitted, collection routes through Zyte.
3. **Alternative Source Discovery**: If Zyte is unconfigured or if Zyte also fails, DataPilot marks the source as blocked, immediately halts requests to it, and queries `SourceDiscovery` to locate and collect from alternative eligible sources.

```
HTTP Collector
      │
      ▼
CAPTCHA Challenge Encountered
      │
      ▼
Zyte Configured & Permitted?
     ├── YES ──► Zyte Adapter ──► Success ──► Raw Document Store
     │                 │
     │               FAILS
     │                 │
     └── NO  ──────────┴──► Mark Source BLOCKED (Zero bypass attempt)
                                   │
                                   ▼
                           Source Discovery
                                   │
                                   ▼
                       Find Alternative Sources
                                   │
                                   ▼
                           Collect from Alternatives
```

---

### 📋 Schemas & Models

#### 1. CollectionRequest Schema
```json
{
  "request_id": "colreq_123",
  "workflow_id": "workflow_123",
  "objective": "Find Indian AI startups founded after 2020 with funding above $5M",
  "entity": "startup",
  "required_fields": ["company", "founders", "website", "funding", "funding_date", "investors"],
  "constraints": {
    "country": "India",
    "industry": "AI",
    "founded_after": 2020,
    "funding_above": 5000000
  },
  "source_preferences": ["Y Combinator Directory"],
  "collection_strategy": {
    "allow_api": true,
    "allow_web": true,
    "allow_public_datasets": true,
    "allow_rss": true,
    "allow_zyte": true
  },
  "limits": {
    "max_sources": 10,
    "max_documents": 1000
  }
}
```

#### 2. CollectionResult Schema
```json
{
  "job_id": "job_123",
  "request_id": "colreq_123",
  "status": "COMPLETED",
  "documents": [
    {
      "document_id": "doc_001",
      "source_id": "source_ycombinator_directory",
      "url": "https://www.ycombinator.com/companies",
      "canonical_url": "https://www.ycombinator.com/companies",
      "content_type": "text/html",
      "status_code": 200,
      "content_location": "storage://documents/doc_001",
      "content_hash": "sha256:abc...",
      "collected_at": "2026-09-27T10:30:00Z",
      "size_bytes": 14200,
      "collector": "http",
      "zyte_used": false
    }
  ],
  "metadata": {
    "sources_discovered": 5,
    "sources_used": 3,
    "pages_collected": 12,
    "documents_collected": 12,
    "failed_urls": 0,
    "duration_ms": 4200,
    "zyte_used": false,
    "alternative_sources_used": []
  },
  "errors": []
}
```

---

### 📡 Phase 4 REST API Endpoints

- `POST /api/v1/collection/jobs`: Creates a collection job from a `CollectionRequest`.
- `POST /api/v1/collection/jobs/{id}/discover`: Discovers eligible sources for the job without executing scraping.
- `POST /api/v1/collection/jobs/{id}/execute`: Executes full collection across selected sources.
- `GET /api/v1/collection/jobs/{id}`: Returns job state, audit statistics, and duration.
- `GET /api/v1/collection/jobs/{id}/documents`: Returns paginated raw documents collected for the job.
- `GET /api/v1/sources`: Lists registered data sources.
- `POST /api/v1/sources`: Registers a new source.
- `GET /api/v1/sources/{id}`: Retrieves details for a specific data source.

---

### ⚙️ Environment Configuration

Add the following to `.env`:

```env
# Phase 4: HTTP & Collector Settings
DATAPILOT_HTTP_TIMEOUT=20
DATAPILOT_HTTP_MAX_RETRIES=3
DATAPILOT_HTTP_USER_AGENT=DataPilot/0.1 (+https://datapilot.dev/bot)
DATAPILOT_REQUESTS_PER_DOMAIN=5
DATAPILOT_MIN_REQUEST_INTERVAL=1.0
DATAPILOT_MAX_DOCUMENT_SIZE_MB=10

# Optional: Zyte Provider Fallback
ZYTE_API_KEY=
ZYTE_API_URL=https://api.zyte.com/v1/extract
```

---

### 🧪 Database Migrations

Apply the database schema using Alembic (versioned migrations):

```bash
cd apps/server
alembic upgrade head
# Or via the helper entry point:
python -m app.db.migrate
```

---

### 🚀 Complete End-to-End Example

**Requirement:**
> *"Find Indian AI startups founded after 2020 with funding above $5M. Give me company, founders, website, funding, funding date and investors."*

1. **Phase 2 (Parser)**: Converts natural language into `StructuredRequirement` (`entity="startup"`, `location={"country": "India"}`).
2. **Phase 3 (Planner)**: Generates DAG containing `DISCOVER_SOURCES`, `COLLECT_DATA`, and downstream steps.
3. **Phase 4 (Collection Engine)**:
   - `SourceDiscovery` queries `SourceRegistry` and selects matching sources (Startup India API, Y Combinator, TechCrunch Feed).
   - `SourceRouter` routes Startup India to `APICollector` and Y Combinator to `HTTPCollector`.
   - `CollectionManager` fetches raw HTML/JSON, applies domain rate limiting, handles retries, and checks canonical cache.
   - If an HTTP source returns a CAPTCHA challenge:
     - Zyte fallback is attempted if `ZYTE_API_KEY` is present.
     - If Zyte fails or is unconfigured, the source is marked `BLOCKED`, and alternative sources (e.g. Wellfound, Crunchbase) are discovered and collected.
   - `RawDocumentStore` hashes and stores verbatim documents in PostgreSQL.
   - Returns a `CollectionResult` referencing all collected raw documents for downstream Phase 5 extraction.
