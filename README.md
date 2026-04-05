# 🎯 Project Dharma MHRG

> **A Fully Automated, 100% Free, Event-Driven Career Operating System.**

Finding jobs, filtering out noise, tweaking LaTeX resumes for Applicant Tracking Systems (ATS), and tracking hundreds of applications manually is a soul-crushing loop. **Project Dharma MHRG** aims to automate the entire process: acting as a private recruitment pipeline where you are the only client.

---

## 🏗️ Core Architecture & The 5-Stage Pipeline

Project Dharma is a heavily decoupled, event-driven microservice system that relies entirely on a free-tier stack. It moves data along 5 distinct stages through a Redis message broker, strictly validating state with Pydantic schemas.

```mermaid
graph TD
    JobBoards[🌐 Job Boards] -->|Playwright Scrapes URLs| Scout[🕵️‍♂️ Scout Agent]
    
    subgraph Event-Driven Processing Pipeline
        Scout -->|Raw Job Data| Redis_Scrape[(Redis: scrape_queue)]
        Redis_Scrape --> Filter[🛡️ Filter Agent]
        
        Filter -->|Pydantic Validates| DB[(🐘 PostgreSQL Database)]
        Filter -.->|Invalid Data| DB_Error[(❌ Error Log)]
        
        DB -->|Queue Valid Jobs| Redis_Tailor[(Redis: tailor_queue)]
        Redis_Tailor --> Tailor[✂️ Tailor Agent <br> 'The Surgeon']
        
        Tailor <-->|Extracts & Formats| LLM[🧠 Groq / Gemini LLM]
        Tailor -->|Injects Data| Latex[📄 Jinja2 + pdflatex]
        Latex -->|Generated| PDF[📁 Custom PDF Resume]
        
        Tailor -->|Queue Metadata| Redis_Sync[(Redis: sync_queue)]
        Redis_Sync --> Sync[🔄 Sync Agent <br> 'Command Center']
        Sync -->|Pushes Data & PDF| Notion[📊 Notion Database]
    end
    
    subgraph Automated Application Tracking
        Gmail[📧 Gmail Inbox] -->|Scans for Updates| Track[🤖 Track Agent <br> 'Coordinator']
        Track <-->|Classifies Interview/Reject| LLM
        Track -->|Updates Job Status| DB
        Track -->|Syncs Kanban Board| Notion
    end
```

### The 5 Stages Explained:
1. **Scout (The Scraper)**: Continuously pulls URL payloads from job boards matching your strategy. Uses Playwright for stealth navigation, scrapes the DOM, and queues the raw job description.
2. **Filter**: Validates incoming listings structurally via deep Pydantic boundaries. Bounces malformed listings before they trigger expensive operations.
3. **Tailor (The Surgeon)**: Operates an LLM via Groq/Gemini to extract a custom summary and bullet points from the job description. Injects the result locally into a `.tex` template via jinja2, then compiles a final, perfectly tailored PDF using `pdflatex` Subprocesses.
4. **Sync (The Command Center)**: Pushes the custom PDF resume and metadata straight to a Notion Database for a centralized visual command center.
5. **Track (The Coordinator)**: Read-only background sync using the Google Workspace (Gmail) API. Scans for interview invites or rejections on APPLIED job entries, uses LLM classification on the email body, and automatically updates tracking status in the database.

---

## 🛠️ The Tech Stack (100% Free Tiers)

- **Database Engine**: PostgreSQL (Local Docker or Supabase Free Tier)
- **Message Broker**: Redis (Local Docker)
- **Job Queues & Workers**: Celery (or RQ)
- **LLM Provider**: Groq API (Llama 3 / Mixtral for extreme speed) or Gemini Free Tier
- **Scraper Engine**: Playwright (Headless Chromium)
- **PDF Generation**: jinja2 + TeX Live (`pdflatex`)
- **API & Core Logic**: Python 3.12+, FastAPI, SQLAlchemy, Pydantic 2.0
- **External Dashboards**: Notion API client

---

## ⚖️ Engineering Guiding Principles

If you are developing this system, you **MUST** adhere to the following absolute rules:

1. **Pydantic First Data Boundaries**: Malformed data is deadly. Every service enforces strict schema validation as its very first operation. A bad payload is immediately diverted to the `ERROR` status log.
2. **Graceful Degradation**: Deep `try/except` blocks encase all scraping and LLM parsing calls.
3. **Idempotency**: Identical URLs or operations sent twice will never result in dual processing or duplicated PDFs.
4. **Decoupled Multi-Agent Network**: Agents (Scout, Surgeon, Coordinator) do not call each other directly. They interact *exclusively* by querying the Postgres database and posting job UUIDs up/down the Redis queues.

---

## 🚀 Advanced Setup & Installation Guide

### Prerequisites
- **Python 3.12+**
- **Docker Desktop** (For local Postgres and Redis queues).
- Accounts for [Groq](https://console.groq.com/) and [Notion](https://developers.notion.com/).

### 1. Environment Initialization
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install uv
uv pip install -r requirements.txt
playwright install
```

### 2. Environment Variables (`.env`)
Create a `.env` file in the root directory:

```env
# Database & Broker
DATABASE_URL=postgresql://user:password@localhost:5432/dharma
REDIS_URL=redis://localhost:6379/0

# LLM Providers
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...

# Command Center
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=...
```

### 3. Running the Microservices
**Start the Message Broker & Database (Docker):**
```bash
docker run -d -p 6379:6379 redis:latest
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:latest
```

**Start the Celery Worker Fleet:**
```bash
# This node will natively spin up and listen to the scrape_queue, tailor_queue, and sync_queue channels
celery -A worker.celery_app worker --loglevel=info
```

**Start the FastAPI Endpoints:**
```bash
uvicorn api.main:app --reload
```
