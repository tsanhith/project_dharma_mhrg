# Phase 7: The Profile Engine & The Radar

## Overview
Phase 7 transitioned **Project Dharma** from a manual, hardcoded pipeline into a fully autonomous, personalized job-hunting machine. Previously, the system relied on manual URL inputs and hardcoded "JOHN DOE" details to render resumes. 

With the completion of Phase 7, the system now autonomously searches for matching jobs via The Radar, checks them against your true skills, and seamlessly injects your actual work history into the LaTeX generation process.

---

## 1. The Profile Engine (Database & API)
To ensure the LLM generates accurate and realistic resume bullets, we needed a "ground truth" to serve as your profile.

**What was done:**
- **`database/models.py`:** Added a new `UserProfile` SQLAlchemy model. Fields include `name`, `email`, `phone`, `location`, URLs (LinkedIn, GitHub, Portfolio), `base_skills`, and a crucial `base_resume_text` field (which stores your entire real work history).
- **`database/schemas.py`:** Created Pydantic shapes (`UserProfileCreate`, `UserProfileResponse`) for safe API data validation.
- **`main.py` (FastAPI):** Added two new endpoints:
  - `GET /api/profile`: Retrieves your profile record (auto-creating a default one if none exists).
  - `POST /api/profile`: Accepts form data from the frontend to update your profile seamlessly and saves it to the PostgreSQL database.

---

## 2. The Command Center: Profile UI
The web dashboard lacked a way to manage your identity.

**What was done:**
- **`templates/frontend/index.html`:** Added a robust, Tailwind-styled "Profile Settings" button and modal overlay.
- It dynamically fetches your current profile via `GET /api/profile` when opened.
- You can now input your base resume text into the text area. 
- Form submission triggers the `POST /api/profile` route, saving it to state and reloading the dashboard automatically.

---

## 3. Dynamic Tailoring (The Sturgeon Update)
The `tailor` agent previously fabricated bullet points based solely on the job description and injected them into a hardcoded "JOHN DOE" template.

**What was done:**
- **`agents/tailor.py`:** 
  - Rewritten to query the active `UserProfile` directly from the database prior to processing.
  - The Groq LLM prompt was upgraded. It now feeds the `base_resume_text` directly to Llama 3.1. It instructions the model: *"You MUST ONLY rely on the candidate's Base Resume Text... DO NOT invent new experiences."* This severely cuts down on LLM hallucinations.
  - Replaced the hardcoded Jinja variables (`candidate_name='JOHN DOE'`) with live attributes (`candidate_name=profile.name`, `email=profile.email`, etc.) when compiling the LaTeX PDF.

---

## 4. The Radar (Job Discovery Agent)
We needed a way to feed the top of the funnel autonomously without constantly blocking Playwright on anti-bot CAPTCHAs.

**What was done:**
- **`agents/radar.py`:** Created a new asynchronous discovery agent.
- **API Ingestion:** Utilizes `httpx` to hit the Remotive API (`https://remotive.com/api/remote-jobs?category=software-dev`), pulling the latest 20 remote tech jobs.
- **Deduplication Check:** Checks the PostgreSQL `JobPipeline` table first yielding safely if a URL is already logged.
- **Lightweight LLM Matcher:** If the job is new, it pings Groq (`llama-3.1-8b-instant`) with your `UserProfile.base_skills` against the API's returned job description. It strictly evaluates if it's a "YES" or "NO" match.
- **Handoff:** If marked "YES", the URL is immediately inserted into the database as `PENDING`, and the `agents.scraper.scrape_job` Celery task is dispatched.

---

## 5. Autonomous Scheduling (Celery Beat)
The Radar agent needed a heartbeat to run entirely hands-free.

**What was done:**
- **`worker.py`:** Addressed structural circular imports and integrated `celery.schedules.crontab`.
- Created a wrapper task `execute_radar()` which runs the asyncio event loop for `agents.radar.run_radar()`.
- Added the `beat_schedule` configuration, telling the Celery worker cluster to execute The Radar **every 4 hours** exactly (configurable via `crontab(minute=0, hour='*/4')`).

---

## Current System Pipeline Flow
1. **[BEAT]** Every 4 hours, `worker.py` executes The Radar.
2. **[RADAR]** Checks Remotive API, validates against your `UserProfile`, injects matches to DB.
3. **[SCOUT / SCRAPER]** Wakes up, uses Playwright to aggressively clean and scrape the matched URL, strips bad HTML, saves text.
4. **[THE TAILOR]** Connects your `UserProfile` ground truth to the cleaned JD via Groq, forces LaTeX compilation.
5. **[THE SYNC]** Relocates generated PDF to `Documents/Ready_Resumes` and updates your Notion Kanban to **READY**.

## Next Steps (Phases 8 & 9)
With discovery and PDF creation heavily automated, **Phase 8** will tackle the "Application Bridge" (a mechanism to auto-inject your details into job applications). **Phase 9** will handle "The Secretary" loop, hooking into your Gmail to track employer responses based on the pipelines.
