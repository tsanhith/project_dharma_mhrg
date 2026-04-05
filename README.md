# Project Dharma MHRG

> **A Fully Automated, 100% Free, Event-Driven Career Operating System.**

Finding jobs, filtering out noise, tweaking LaTeX resumes for Applicant Tracking Systems (ATS), and tracking hundreds of applications manually is a soul-crushing loop. **Project Dharma MHRG** aims to automate the entire process: acting as a private recruitment pipeline where you are the only client.

## ?? Core Architecture & The 5-Stage Pipeline

Project Dharma is a heavily decoupled, event-driven microservice system that relies entirely on a free-tier stack. It moves data along 5 distinct stages through a Redis message broker, strictly validating state with Pydantic schemas.

1. **Scout (The Scraper)**: Continuously pulls URL payloads from job boards matching your strategy. Uses Playwright for stealth navigation, scrapes the <body> element, and queues the raw job description.
2. **Filter**: Validates incoming listings structurally via deep Pydantic boundaries. Bounces malformed listings before they trigger expensive (or time-consuming) operations.
3. **Tailor (The Surgeon)**: Operates an LLM via Groq/Gemini to extract a custom summary and bullet points from the job description. Injects the result locally into a .tex template via jinja2, then compiles a final, perfectly tailored PDF using pdflatex Subprocesses.
4. **Sync (The Command Center)**: Pushes the custom PDF resume and metadata straight to a Notion Database for a centralized visual command center.
5. **Track (The Coordinator)**: Read-only background sync using the Google Workspace (Gmail) API. Scans for interview invites or rejections on APPLIED job entries, uses LLM classification on the email body, and automatically updates tracking status in the database.

## ??? The Tech Stack (100% Free Tiers)

*   **Database Engine**: PostgreSQL (Local Docker or Supabase Free Tier)
*   **Message Broker**: Redis (Local Docker)
*   **Job Queues & Workers**: Celery (or RQ)
*   **LLM Provider**: Groq API (Llama 3 / Mixtral for extreme speed and rate limits) or Gemini Free Tier
*   **Scraper Engine**: Playwright (Headless Chromium)
*   **PDF Generation**: jinja2 + TeX Live (pdflatex)
*   **API & Core Logic**: Python 3.12+, FastAPI, SQLAlchemy, Pydantic 2.0
*   **External Dashboards**: Notion API client

## ??? Engineering Guiding Principles

If you are developing this system, you **MUST** adhere to the following absolute rules:

1.  **Pydantic First Data Boundaries**: Malformed data is deadly. Every service enforces strict schema validation as its very first operation. A bad payload is immediately diverted to the ERROR status log, preserving the main loop.
2.  **Graceful Degradation**: Deep 	ry/except blocks encase all scraping and LLM parsing calls. If Playwright times out or Groq generates invalid JSON, the system does NOT crash. The row updates to ERROR enum status, capturing the traceback, and Celery moves to the next message.
3.  **Idempotency**: Identical URLs or operations sent twice will never result in dual processing or duplicated PDFs. Unique database constraints protect the processing pipeline.
4.  **Decoupled Multi-Agent Network**: Agents (Scout, Surgeon, Coordinator) do not call each other directly. They interact *exclusively* by querying the Postgres database and posting job UUIDs up/down the Redis queues.

---

## ?? Advanced Setup & Installation Guide

### Prerequisites
1.  **Python 3.12+**
2.  **Docker Desktop** (For local Postgres and Redis queues).
3.  **TeX Live / MiKTeX**: You must have pdflatex available in your system path.
4.  Accounts for [Groq](https://console.groq.com/) and [Notion](https://developers.notion.com/).

### 1. Environment Initialization
Clone the repository and spin up your isolated virtual environment using uv for blazing-fast installations.

`powershell
python -m venv venv
.\venv\Scripts\activate
pip install uv
uv pip install -r requirements.txt
playwright install
`

### 2. Environment Variables (.env)
Create a .env file in the root directory:

`env
# Database & Broker
DATABASE_URL=postgresql://user:password@localhost:5432/dharma
REDIS_URL=redis://localhost:6379/0

# LLM Providers
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...

# Command Center
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=...

# Gmail Integration (OAUTH)
GOOGLE_CREDENTIALS_FILE=credentials.json
`

### 3. Running the Microservices

*Project Dharma requires running separate isolated workers to consume queues asynchronously.*

**Start the Message Broker & Database (Docker):**
`ash
docker run -d -p 6379:6379 redis:latest
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:latest
`

**Run the Database Migrations (Initial Setup):**
*(Run your SQLAlchemy engine scripts to scaffold schemas)*
`ash
python scripts/init_db.py
`

**Start the Celery Worker Fleet:**
`ash
# This node will natively spin up and listen to the scrape_queue, tailor_queue, and sync_queue channels
celery -A worker.celery_app worker --loglevel=info
`

**Start the FastAPI Endpoints:**
`ash
uvicorn api.main:app --reload
`

---

## ?? Project Directory Structure

`	ext
project_dharma_mhrg/
¦
+-- agents/                  # The isolated worker logic
¦   +-- scraper.py           # Playwright DOM parsers
¦   +-- tailor.py            # Local LLM -> Jinja2 -> PDFtex inject
¦   +-- notion_sync.py       # Pushes compiled data to Notion DB
¦   +-- coordinator.py       # Gmail tracking sync processor
¦
+-- database/                # Pydantic & SQLAlchemy Models
¦   +-- db.py                # Postgres Engine initialization
¦   +-- models.py            # Strict ORM Tables (JobStatus, JobPipeline)
¦   +-- schemas.py           # Pydantic shapes ensuring 100% data validity
¦
+-- templates/               # LaTeX Source Files
¦   +-- resume_base.tex      # The master LaTeX Jinja2 template
¦
+-- worker.py                # Celery App entrypoint & Queue routing
+-- .env.example             # Shared variables list
+-- requirements.txt         # Core dependencies
+-- README.md                # Project architecture schema
`

## ?? Standard Operating Procedure (SOP) when contributing

Before pushing code or altering logic in Agent segments:
1. Verify models.py allows your state transition (e.g., PENDING -> SCRAPED).
2. Add comprehensive Pydantic checking to your specific AgentState.
3. Never use external Paid API services (OpenAI etc.). Keep to the 100% Free Stack policy.
