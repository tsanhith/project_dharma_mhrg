# Project Dharma MHRG - Phase 5 Complete Documentation
## Automated Notion Command Center Sync

### Overview
Following the successful implementation of Phase 4 (The Surgeon / LaTeX ATS Resume Generation), Phase 5 focused on building the "Command Center". The objective was to seamlessly bridge the gap between the local backend pipeline (Postgres/Redis/Celery) and a user-facing dashboard where all parsed jobs, generated resumes, and statuses could be managed. We chose Notion via its REST API (version `2022-06-28`) as the visual frontend.

---

### 1. Database and Environment Configuration
Before establishing the Notion connection, we needed to ensure the local environment was robust enough to handle the data passing between workers and the API gracefully.

- **PostgreSQL Stabilization**: We resolved connection loop errors and missing schema constraints (`relation "job_pipeline" does not exist`) by executing SQLAlchemy ORM's `metadata.create_all()`. We explicitly mapped the DB connection string to use URL-encoded passwords (`%40` instead of `@`) and tied it strictly to the `postgres` driver in `.env`.
- **Environment Encoding Fix**: PowerShell was saving the `.env` file using UTF-16LE, which injected `embedded null character` errors into Python's `python-dotenv` reader. We diagnosed this by tracking raw byte outputs and rewrote `.env` strictly enforcing UTF-8 encoding.
- **Queue Segregation**: We refactored `worker.py` to ensure Celery accurately listened to specific tasks rather than generic queues. We deployed `-Q queue,scrape_queue,tailor_queue,sync_queue`.

---

### 2. The Notion Sync Agent (`agents/notion_sync.py`)
With the PDF correctly compiling in Phase 4, we built an isolated asynchronous agent responsible solely for network calls to Notion. 

#### Trigger Condition
The task (`sync_to_notion`) only executes when a job transitions to `JobStatus.TAILORING` (meaning the PDF compilation step was successful).

#### Payload Architecture
The Agent maps our PostgreSQL schema directly into Notion's heavily typed JSON block structures:

1. **Title Mapping (`title` / `rich_text`)**: Extracts the `job.title` and `job.company` and cleanly formats them into a single string (`Senior AI Architect @ CyberDyne Systems`) mapped directly into the primary column of the Notion database.
2. **URL Mapping (`url`)**: Drops the scraped job posting URL into the dedicated `Job URL` property.
3. **Local References (`rich_text`)**: Explicitly saves the absolute path of the generated PDF (`output_pdfs/resume_UUID.pdf`) onto the board so the user can immediately locate the custom resume locally.
4. **State Management (`status`)**: We encountered a schema validation error where our script attempted to send a "Select" object. By querying the live user Notion database schema directly, we identified that the `Status` column was set as a native `status` property. We mapped the payload to automatically update the card to `"Ready to Apply"`. 

#### Content Injection (Page Body)
Rather than cluttering the spreadsheet view, we utilized Notion's `children` block array structure. The sync agent appends a `heading_2` block ("Raw Job Description") and a `paragraph` block directly into the page itself, dumping the massive raw scraped data so it's readily accessible when clicking "Open" on the row.

---

### 3. Pipeline Integration & Testing
We verified the integrity of the full architecture via an end-to-end integration test rather than isolated unit tests.

1. **Test Job Creation**: A Python script was run to mock an incoming job object. It generated a unique UUID, appended dummy text ("We are looking for a Senior AI developer with experience in 5 years of Python..."), set the database flag to `JobStatus.SCRAPED`, and pushed it directly into `tailor_queue`.
2. **Phase 4 Hand-off**: The Celery worker successfully recognized the `tailor_queue` task, used the Groq API (`llama-3.1-8b-instant`) to parse the JSON, and compiled the LaTeX PDF seamlessly.
3. **Phase 5 Delivery**: Upon successful generation, Phase 4 dispatched a new message to `sync_queue`. The `sync_to_notion` agent picked it up, constructed the JSON headers, authorized via `Bearer` token securely stored in `.env`, and fired the POST request.

**Result**: The automated job pipeline completely bypassed manual entry. A simulated scraped job was automatically digested, reasoned upon, compiled into a formatted PDF resume, and organized onto a live Kanban Notion Board within seconds.

---

### Summary of System State at Phase 5 Conclusion
- Scraper logic connects to PostgreSQL.
- PostgreSQL passes signals through Redis.
- Free-Tier MiKTeX engine compiles strictly 1-page ATS resumes.
- Notion Command Center receives all metadata and long-form raw context.
- System is prepared for scaled Phase 6 execution (Auto Applying).