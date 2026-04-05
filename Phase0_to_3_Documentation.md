# Project Dharma MHRG - Deep Architecture Documentation (Phases 0 - 3)

This architectural log explicitly outlines the foundation of Project Dharma MHRG. It is written to serve as both an onboarding document for new agents/developers and a strict record of the 100% Free-Tier mandate constraints applied during configuration.

---

## Phase 0: Project Initialization & Environment Isolation

### The Goal
Establish a pristine, isolated, and lightning-fast Python execution environment. Given the heavy processing nature of the project (Generative AI, Web Scraping, PDF Compilation), leaking dependencies into a global Windows environment causes insurmountable versioning conflicts. 

### Implementation Details
1. **Virtual Environment Isolation**: Created a pure Python sandbox using python -m venv venv.
2. **High-Speed Dependency Tracking (uv)**: Standard pip struggles with massively interconnected libraries like SQLAlchemy, Celery, and Playwright. We used uv (a Rust-backed package manager) to compile and resolve dependencies up to 100x faster than standard pipelines.
3. **equirements.txt Blueprint**: Enforced the zero-cost architecture by strictly defining:
   - astapi & uvicorn: Framework for potential frontend bridging.
   - sqlalchemy & psycopg2-binary: Relational mapping for the PostgreSQL state engine.
   - pydantic & pydantic-settings: In-flight memory validation.
   - celery & edis / eventlet: Event-driven task queues.
   - groq: Our exclusive LLM provider (bypassing OpenAI costs).
   - playwright: Headless browser interactions.
   - jinja2: Template engine mapping for future LaTeX rendering.

---

## Phase 1: The Foundation (Data Boundaries & Postgres Schemas)

### The Goal
The backbone of "Project Dharma" is ACID compliance. A job description text is inherently messy. We rely on PostgreSQL to enforce strict state-machine rules so that parallel workers do not accidentally process the exact same application twice, nor fail quietly due to malformed metadata.

### Implementation Details & File Architecture
*   **database/db.py**:
    *   Hosts the core SQLAlchemy create_engine() logic.
    *   Ingests the DATABASE_URL heavily relying on PostgreSQL credentials (postgresql://user:password@localhost:5432/db).
    *   Defines the SessionLocal generator used throughout the various detached agents.
*   **database/models.py**:
    *   Defines physical layout constraints in PostgreSQL.
    *   Created JobStatus(enum.Enum) to strictly boundary rows to 6 exact states: PENDING, SCRAPED, TAILORING, READY, APPLIED, ERROR. If a worker attempts to save an invalid state, PostgreSQL fatally rejects the transaction, preventing database corruption data-drift.
    *   Created JobPipeline(Base). The primary key is forcefully set to a UUID string to avoid integer-guessing attacks. url is marked as unique=True so accidentally pushing identical job links bounces instantly via Native SQL Constraint.
*   **database/schemas.py**:
    *   Establishes **Pydantic Model Validations**. 
    *   Acts as a gatekeeper: Incoming payload dictionaries are mapped dynamically against JobCreate and JobResponse. If a dict is missing a URL, Pydantic throws a ValidationError *before* connecting to Postgres, saving expensive DB cycles and bandwidth.

---

## Phase 2: The Message Broker (Redis & Celery Workers)

### The Goal
Escape the synchronous scripting paradigm. High I/O tasks like loading the DOM of heavily cached single-page applications (e.g., LinkedIn) block Python's main thread. By implementing a Message Broker, we decouple operations: an event fires a simple string UUID into a queue, and background workers process them independently "off the main thread." 

### Implementation Details
1. **The Post Office (Memurai/Redis)**:
   - Installed Memurai as an active Windows background service on localhost:6379. It functions identically to Redis, storing rapid-fire, volatile JSON tickets purely in memory.
2. **The Worker Setup (worker.py)**:
   - Initialized celery_app = Celery("dharma_worker"). 
   - Overrode default celery behavior by strictly defining celery_app.conf.task_routes. 
   - We provisioned three physical "bins" or channels in Redis: scrape_queue, 	ailor_queue, and sync_queue. Tasks are forcefully shunted to target boundaries depending on the namespace of the Agent executing them (e.g., gents.scraper.* -> scrape_queue).
3. **Thread Pool Subversion**:
   - Windows natively lacks OS-level fork processes (essential to default Celery performance). We deliberately boot Celery via pip install eventlet or using -P solo flags to force execution via Thread Pools or Solitary processing to mitigate Windows thread-locking warnings.

---

## Phase 3: Segment A - The Scout (Playwright Scraper)

### The Goal
Construct "Robot 1". The automated system must query a URL, visually render any dynamic Javascript, capture the HTML body, bypass rate-limiting UI elements, save the text to Postgres, and hand off the workload.

### Implementation Details
1. **Playwright Ecosystem**:
   - Installed chromium via Playwright CLI. Playwright operates by downloading actual headless web-browser executable binaries directly over the API, bypassing native driver incompatibilities.
2. **The Agent Code (gents/scraper.py)**:
   - Implements @celery_app.task(name='agents.scraper.scrape_job'). This decorator physically binds the Python function to a Celery worker listening on the scrape_queue.
   - **Internal Logic Execution Loop**:
     1. Receives job_id UUID payload.
     2. Instantiates a scoped db = SessionLocal().
     3. Checks atomic correctness (If a job is NOT PENDING, exit gracefully - known as Idempotent operation testing).
     4. Invokes sync_playwright(). Explicitly defines a huge **30000ms delay** on page.goto(wait_until='networkidle') to allow modern React/Angular applications to fully hydrate the DOM before we attempt text extraction via .locator("body").inner_text().
     5. Updates the Postgres model directly: status = JobStatus.SCRAPED, writes aw_jd_text.
     6. **The Hand-off**: Fires celery_app.send_task('agents.tailor.tailor_resume', args=[job_id]). Passes the UUID immediately down the conveyor belt to the next agent.
   - **Graceful Degradation Design**: 
     - Entire block is shielded in a strict 	ry/except. If the web-scraper is geo-blocked, times out, or fails to hydrate, the script intercepts the exception. It pushes JobStatus.ERROR and writes the Python Traceback string directly to Postgres error_message. It specifically avoids throwing unhandled errors to avoid crashing the Celery worker loop. 
