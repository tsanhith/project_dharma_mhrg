# Phase 9: The Secretary - Automated Inbox Monitoring & CRM Tracking

## Overview
Phase 9 transitioned Project Dharma from an outward-facing application generator into a fully closed-loop CRM. Prior to this phase, the pipeline ended at the `APPLIED` state. If a recruiter reached out for an interview or sent a HackerRank test via email, the user had to manually track it outside of the system. 

The goal of Phase 9 was to build **The Secretary** (`agents/secretary.py`): an autonomous background agent that acts as your personal proxy. It wakes up on a schedule, scans simulated inbox responses from employers, leverages the Groq LLM to instantly classify the intent of unstructured employer emails (Interview, Assessment, Rejection), and visually updates the command center UI.

---

## 1. Expanding the State Machine (PostgreSQL Enums)
To properly govern the data structure, the underlying state machine holding `JobPipeline` together needed new enumerated values.

**Implementation Details:**
- Modified `database/models.py` to append three long-tail states directly to the `JobStatus` Enum:
  - `INTERVIEW`: Indicates human interaction or recruiter scheduling.
  - `ASSESSMENT`: Indicates a technical screen, HackerRank, or asynchronous HireVue task has been assigned.
  - `REJECTED`: Indicates a standard cold rejection.

**Architectural Challenge Encountered:**
- **Problem**: When simply appending new values to the Python SQLALchemy enum array, PostgreSQL violently rejected state updates (`InvalidTextRepresentation`). `Base.metadata.create_all` does *not* automatically run `ALTER TYPE` on enums that already existed in previous migrations.
- **Resolution**: Had to forcibly bypass SQLAlchemy's ORM and manually inject raw SQL into the database engine block in an `AUTOCOMMIT` envelope:
  `ALTER TYPE jobstatus ADD VALUE 'INTERVIEW';`
- This accurately stitched the new Python backend state seamlessly into the strict Postgres typing system.

---

## 2. The Inbox Sweeper: Fetching Mechanics
Fetching live IMAP or OAuth 2.0 Gmail sequences inherently introduces complex auth-expiry problems that block local prototyping. A simulated fetcher function was developed.

**Implementation Details:**
- Built `fetch_mock_emails_for_company(company_name)` inside `secretary.py`.
- It acts as an integration-ready wrapper. The agent loops over any `JobPipeline` object possessing an `APPLIED` status. It then fuzzy-matches the `company_name` string against a nested mocked payload (e.g. associating "Google Inc" with a rejection payload).
- This structure enables you to immediately rip out the dictionary mockup in the future and inject `google-api-python-client` logic seamlessly without altering the entire file.

---

## 3. Intent Classification via LLM Constraint (Groq)
Parsing recruiter emails is heavily nuanced. A simple substring search for the word "Test" or "Sorry" is computationally destructive and yields high false-positive rates.

**Implementation Details:**
- Integrated `llama-3.1-8b-instant` through the Groq SDK entirely.
- Engineered a highly restrictive system prompt:
  > *"Given the Subject and Body of the email, categorize it strictly into ONE of the following tags: INTERVIEW, ASSESSMENT, REJECTED, or UNKNOWN... Respond ONLY with the exact tag word. Do not include any other text."*
- Bounded the `temperature` rigidly to `0.0`.
- The deterministic classification parses natural conversational English ("We'd love to chat") directly into programmatic CRM values (`JobStatus.INTERVIEW`), acting perfectly as an interpretation bridge.

---

## 4. UI Rendering Updates (Jinja2 & Tailwind)
The core web application needed a way to signal to the user that the background beat had intercepted something important.

**Implementation Details:**
- Extensively updated `index.html` within the Jinja conditional iterating block.
- Previously halted at `"Pipeline Started" (PENDING)`. 
- Appended high-priority UI badges utilizing Tailwind CSS classes:
  - **Interview Scheduled!**: A glowing `@animate-pulse` yellow badge (`bg-yellow-100 text-yellow-800`) grabs instant visual attention.
  - **Assessment Pending**: A bright orange badge (`bg-orange-100`) signaling urgent tasks are queued.
  - **Rejected**: A dark bordered red badge (`bg-red-900 border-red-700 text-red-200`) signaling the terminal state has been achieved safely.

---

## 5. Autonomous Pulse Cycle (Celery Beat)
The Secretary requires total independence. It should not rely on a manual user execution script; you should be able to wake up, look at your Dharma Dashboard, and accurately see which companies messaged you overnight.

**Implementation Details:**
- Integrated `agents.secretary.run_secretary()` inside `worker.py`. 
- Encapsulated into the standard `scrape_queue`.
- Modified `celery.schedules.crontab`:
```python
'run-secretary-daily': {
    'task': 'worker.execute_secretary',
    'schedule': crontab(minute=0, hour='0,12'), 
}
```
- This configures the Celery Beat system to deploy the AI Secretary explicitly twice a day (at noon and midnight) directly sweeping your DB endpoints quietly via background processing.
