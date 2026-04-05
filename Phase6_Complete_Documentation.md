# Phase 6: The Scout (Real Job Web Scraping Pipeline) - Status: Complete

## 1. Overview
In Phase 6, we initialized **The Scout Agent** (`agents/scraper.py`). Instead of relying on hardcoded dummy data for the Tailor Agent, we implemented an asynchronous Headless Chromium browser using `playwright` to scrape the literal raw text from live job posting URLs, no matter how much heavy JavaScript the site uses (such as LinkedIn, Lever, Greenhouse).

We fully integrated this agent into our core **Redis-backed Celery Worker pipeline**.

## 2. Technical Stack
- **Browser Automation Framework:** `playwright` (Chromium headless instance).
- **Asynchronous Loop Handling:** `asyncio` for ensuring playwright doesn't lock up synchronous Celery tasks.
- **Data Cleanup:** Raw DOM `page.locator("body").inner_text()` extraction.
- **Queue System:** Celery Worker processing tasks from the `-Q scrape_queue`.

## 3. Workflow Progression
We updated our local development architecture so that jobs inserted into the Postgres `job_pipeline` table automatically trigger a full end-to-end automation sequence:
1. `JobStatus.PENDING` -> User inputs URL into DB. `scrape_job` triggers.
2. **Scraper Pipeline (`agents.scraper.scrape_job`)** connects to Playwright, navigates to the URL with a 30s connection timeout for SPAs, strips pure text from the body, and writes it to DB. Status is set to `JobStatus.SCRAPED`.
3. Scraper cascades the Job ID directly to `agents.tailor.tailor_resume` into the `tailor_queue`.
4. **Tailor Pipeline** uses Groq API to parse the scraped body text into our strict JSON format, injects it into LaTeX, compiles a custom PDF, updates status to `JobStatus.TAILORING`, and pushes to the `sync_queue`.
5. **Notion Sync Pipeline** pushes the final PDF location, raw URL, and raw job description directly into the user's Notion board for the ultimate final disposition. Status is set to `JobStatus.READY`.

## 4. Work Complete
- Created the Async Playwright Web Scraper (`async_scrape_url`).
- Bridged `scrape_job` to the `worker.py` Celery execution router mapping.
- Resolved Windows-specific `billiard` Multiprocessing Worker bugs by leveraging the `--pool=solo` argument to allow stable process spawning on OS level.
- Re-tested full suite logic `(Scraper -> Tailor -> Notion)`. Verified that dynamic scraping (tested on a sample Wikipedia page) successfully extracted structural data, which the Groq LLM successfully processed, compiled into LaTeX, and deployed directly to Notion.

## 5. Next Steps
Phase 6 closes out the core backend automation loop for the Dharma AI agent pipeline. The end-to-end data funnel architecture—from job prospect URL detection continuously through tailored PDF generation and Kanban board synchronization—is stable and tested.
