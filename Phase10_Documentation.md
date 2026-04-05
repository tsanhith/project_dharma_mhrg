# Phase 10: Real Email Bridge & Dharma OS UI Migration

## Overview & Objectives
Phase 10 represents the most significant leap forward for Project Dharma, transitioning the architecture from a localized terminal-executable prototype into a production-grade Web OS. This phase successfully tackled two massive foundational pillars:
1. **The Real Email Bridge:** We ripped out the hardcoded mock dictionaries in the Secretary Agent and integrated the official Google Cloud Platform (GCP) Gmail API. The background workers now securely authenticate with OAuth 2.0 and read real employer responses from a live inbox.
2. **The Front-End Overhaul ("Dharma OS"):** We completely replaced the basic rudimentary single-page HTML form with a high-fidelity, component-based Jinja2 templated dashboard featuring a "Cyberpunk Executive" aesthetic. 

The culmination of this phase represents a fully realized closed-loop CRM that not only tracks state autonomously but provides a beautiful, Notion-style visual interface for the user.

---

## Part 1: The Real Email Integration (Gmail API)

### 1.1 The Authentication Strategy (OAuth 2.0 Refresh Tokens)
Operating a background polling agent (like Celery Beat) against Google's API presents a unique challenge: Google OAuth tokens expire every hour. A user cannot be expected to click a "Sign In with Google" popup every time the background task runs at 3 AM.

**Implementation Details:**
- Created a GCP project named "Dharma-Secretary" and enabled the `gmail.readonly` scope.
- We opted for a **Desktop App OAuth** flow rather than a Web App flow. This allowed us to explicitly request `access_type="offline"`.
- Created `utils/get_refresh_token.py`:
  - Utilizes `google_auth_oauthlib.flow.InstalledAppFlow`.
  - SpINS up a temporary local server (`port=0`) to catch the Google callback redirect.
  - Retrieves a permanent `Refresh Token` and outputs it directly to the `.env` file under `GOOGLE_REFRESH_TOKEN`.
- **Result:** The system can now silently request a new access token every 4 hours without any user intervention.

### 1.2 Overhauling the Secretary Agent
The `agents/secretary.py` file was completely rewritten to support live API calls.
- **Dependencies Added:** `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`.
- **The Fetch Logic (`fetch_emails_for_company`):**
  - Connects to the Gmail v1 API via `build('gmail', 'v1', credentials=creds)`.
  - Utilizes Google's internal query language to filter fast context: `q=f'"{company_name}" newer_than:7d'`. By only pulling emails newer than 7 days that mention the company name, we drastically reduce token limits natively before the data even hits our pipeline.
- **Payload Parsing:**
  - Gmail API returns `.EML` multi-part boundaries. It does not return simple strings.
  - Wrote a structural parser that iterates through `payload.get('headers')` to extract the `Subject`.
  - Implemented `base64.urlsafe_b64decode` to decode the encrypted body `data` payload into standard UTF-8 UTF-8 text so it can be ingested by the Groq LLM.
- **The Groq Pipeline:** This parsed UTF-8 text is then pushed into our existing strict `llama-3.1-8b-instant` classification prompt to tag the email as `INTERVIEW`, `ASSESSMENT`, or `REJECTED`.

---

## Part 2: Front-End UI Architecture (Dharma OS)

The application required a completely tailored front end to handle the massive amount of asynchronous data being generated. The design mandate was "Dark Mode Notion meets Executive Dashboard." We utilized AI generation (Stitch/Bolt) to rapidly prototype HTML components and injected them into the FastAPI Jinja template system.

### 2.1 Componentizing the Templates
Previously, the system operated on a gross single `index.html` file. Phase 10 separated concerns using standard Jinja `{% extends %}` inheritance to create a Single Page Application (SPA) feel.

**Structure Created:**
- `templates/frontend/base.html`: The structural root. Contains the Tailwind CDN imports, custom Google Fonts (`Space Grotesk`, `Inter`), dark-mode CSS overrides, the SVG noise filter background, and the permanent Left Nav-Bar.
- `templates/frontend/index.html`: (The Radar Feed)
- `templates/frontend/pipeline.html`: (The Kanban CRM)
- `templates/frontend/brain.html`: (User Preferences)

### 2.2 FastAPI Routing Adjustments (`main.py`)
To serve the multi-tab layout without shifting standard application flow, new HTML endpoints were mapped:
- `@app.get("/")`: Maps to the Radar Feed. Injects `jobs` filtered specifically for `PENDING` states.
- `@app.get("/pipeline")`: Maps to the Kanban Board. Injects all `jobs` and sorts them natively inside Jinja `{% for %}` loops.
- `@app.get("/brain")`: Maps to the Profile page. Injects `profile` data so the user can see their Master Resume without querying a separate endpoint.

---

## Part 3: The Three Core Application Views

### View 1: The Radar Feed (`index.html`)
The "Inbox" of the application where the background Scraper logic drops its findings.
- Visually lists glass-paneled High-Fidelity job matches.
- **Backend Wire-Up:** Contains the vital `<form action="/api/jobs/{{ job.id }}/apply" method="POST">`. Clicking the "Auto-Apply" button on any card instantly queries FastAPI and pushes a Playwright execution task to the `Celery scrape_queue`.

### View 2: The Kanban Pipeline (`pipeline.html`)
A horizontal scrolling, multi-column board tracking the exact state machine of `models.JobStatus`.
- **Columns Implemented:**
  1. `PENDING`: Gray/Neutral. Waiting for user action.
  2. `APPLIED`: Neutral state. Waiting on Employer.
  3. `ASSESSMENT`: High-contrast Orange text. Represents a HackerRank or coding test detected.
  4. `INTERVIEW`: Pulsing Neon Yellow `animate-pulse` CSS. Represents a direct human interview request.
  5. `REJECTED`: Faded, low opacity Red. Ghosted applications.
- **Dynamic Routing:** Jinja uses conditional logic `{% if job.status.name == 'INTERVIEW' %}` to map database records directly into their respective columns, effectively making the UI react passively to the Secretary Bot's background actions.

### View 3: The Brain (`brain.html`)
The Configuration center. This holds the user's "Source of Truth" to prevent the LLMs from hallucinating skills.
- Implements dual split-columns. One for hard variables (Name, Phone, Links, Array of Core Skills).
- One massive Text Area for the `Base Resume Text`.
- Updating the form sends a standard `POST` request to `/api/profile`, overwriting the existing Singleton database instance (ensuring we only have ONE master profile) and issues a `RedirectResponse` back to the configuration page.

---

## Final Security & Operational Flow

1. **Environmental Security:** All critical secrets (Groq, Notion, Google Client Secret, Google Refresh Token) are strictly walled inside `.env` configurations. They are not bundled with Git.
2. **Terminal Execution Constraints:**
   - The UI runs via `uvicorn main:app --reload` on port `8000`.
   - The autonomous workers load the `.env` strings implicitly and run asynchronously inside `celery -A worker.celery worker --beat`.

Project Dharma is now visually, conceptually, and programmatically complete with a 2-way real-time data flow connecting a Chrome-based application bot directly to the recruiter's inbox response.