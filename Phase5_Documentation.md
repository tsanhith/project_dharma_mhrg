Project Dharma MHRG - Deep Architecture Documentation (Phase 5)
===============================================================

1. Executive Summary & Core Objective
--------------------------------------
Phase 5, "The Command Center," bridges the execution backend with the user-facing frontend. Once Phase 4 completes generating individual customized, ATS-complaint resumes, it fires off a tracking ID toward exactly one consumer: The Notion Database API.

Its objective is simple yet strict: Provide the user with a scalable spreadsheet view of all parsed jobs via Notion, tracking job statuses without requiring specialized local frontend (React/Next JS) builds. It surfaces the Job Title, Company, direct URL, and local path to the perfectly tailored PDF file that was generated.

2. Architecture & Queue Hand-off
--------------------------------
Upon successful LaTeX compilation, `agents/tailor.py` executes:
`celery_app.send_task('agents.notion_sync.sync_to_notion', args=[job_id], queue='sync_queue')`

The `notion_sync.py` agent is strictly listening on `sync_queue`.
1. The message broker (Redis) instantly forwards the job_id payload.
2. The agent boots an isolated PostgreSQL transaction validating `job.status == JobStatus.TAILORING`. 
3. If it’s stuck in another state, the agent aborts processing to avoid idempotency failures or double-API calls.

3. The Third-Party Integration: Notion API
------------------------------------------
We execute RESTful JSON payloads directly to `api.notion.com`.

- **Authentication**: A standard secret integration token (`NOTION_API_KEY`) is injected as a Bearer Token.
- **Database Mapping**: The payload is sent targeting `NOTION_DATABASE_ID`.
- **Property Mapping**: A hardcoded schema dynamically fills standard notion primitives:
    - `Role / Title` -> Text property
    - `Company` -> Rich Text
    - `Job URL` -> URL Type
    - `Status` -> Select Option (`Ready to Apply`)
    - `Local PDF Path` -> Text path pointing to the locally generated resume on Windows

4. Final States & System Completion
-----------------------------------
A successful `200 OK` response triggers the final transaction:
`job.status = JobStatus.READY`
All worker processes close natively here, officially concluding the full MHRG extraction and crafting pipeline!