# Project Dharma MHRG - Deep Architecture Documentation (Phase 4)

## 1. Executive Summary & Core Objective
Phase 4, also known as "Robot 2" or "The Surgeon," represents the intelligence layer of the Project Dharma MHRG pipeline. Its primary objective is to dynamically process the unstructured text scraped by the Scout agent and transform it into a perfectly tailored ATS-compliant (Applicant Tracking System) dataset. Finally, it injects this data into a LaTeX document and compiles it into a cleanly formatted PDF resume.

This phase is governed by strict constraints:
- Zero financial cost (strictly utilizing the Groq free tier).
- Zero conversational hallucination (enforcing strict JSON boundaries).
- Strict idempotency (never reprocessing the same job twice).
- Graceful degradation (LLM failures or LaTeX syntax errors must not crash the Celery worker).

---

## 2. Architectural Blueprint & Message Brokering
The Surgeon operates completely detached from the Scout. They do not share memory and do not call each other's functions. 
- **Trigger Mechanism**: The agent is bound to the tailor_queue within the Redis message broker via the @celery_app.task decorator.
- **Payload**: The only payload passed over the wire is a single UUID string (job_id). This minimizes Redis memory usage and prevents network bloat.
- **Database Context**: Upon receiving the UUID, the worker spins up an isolated SessionLocal database transaction to fetch the actual payload from PostgreSQL.

---

## 3. Idempotency & Pre-Flight Validations
Before performing any expensive network I/O or LLM inference, the Surgeon executes a series of pre-flight checks:
1. **Existence Check**: Queries the JobPipeline table for the matching UUID. If deleted or missing, the task silently aborts.
2. **State Machine Validation**: Verifies that job.status == JobStatus.SCRAPED. 
   - If the job is PENDING, the Scout hasn't finished.
   - If the job is ERROR, the Scout failed.
   - If the job is TAILORING or READY, a duplicate message was accidentally queued.
   - The worker immediately drops the task if the status is anything other than SCRAPED, completely cementing pipeline integrity and avoiding duplicate generation.

---

## 4. The LLM Engine: Groq and Llama 3 Optimization
To maintain the "100% Free Tech Stack" mandate, Project Dharma intentionally avoids the OpenAI API. Instead, it leverages the Groq API.
- **The Hardware Advantage**: Groq uses LPUs (Language Processing Units) rather than traditional GPUs, providing hundreds of tokens per second. This speed is critical when attempting to process dozens of job applications asynchronously.
- **Model Selection**: We specifically target the llama3-8b-8192 model. This model offers the perfect balance of reasoning capability for ATS analysis and a large enough context window (8192 tokens) to ingest complex job descriptions.

### Context Window Slicing
Web scraping yields extremely dirty data. A single Playwright inner_text() extraction will pull copyright footers, hidden navigation bar items, cookie policies, and irrelevant HTML artifacts.
- To prevent blowing out the LLM's context window and triggering a RateLimitError or TokenLimitExceeded exception, we aggressively slice the incoming text: job.raw_jd_text[:3000].
- 3,000 characters securely captures the meat of a standard job requirement description without overloading the payload.

---

## 5. Prompt Engineering & Strict JSON Enforcement
LLMs are inherently chatty. In a programmatic pipeline, conversational fluff (e.g., "Sure, I can help you with that! Here are the bullet points:") will lethally crash the data parser. 
- **Response Format**: We invoke Groq's native JSON mode using response_format={"type": "json_object"}.
- **System Prompting**: We define the system role explicitly as 'You are a JSON-only API. You output raw valid JSON without markdown wrapping.'
- **Schema Mapping in Prompt**: The prompt explicitly forces the AI to map the extraction to a specific dictionary shape. Length constraints (exactly 4 bullets) are also established to fit the physical bounds of the LaTeX template.

---

## 6. Pydantic Runtime Gatekeeping
Despite prompt constraints, AI hallucination is always a risk. The LLM might return misspelled keys (bullet_points instead of bullets), nested arrays, or invalid datatypes.
- **The Gatekeeper**: We define a strict Pydantic BaseModel logic block in Python.
- **Instant Validation**: The output from the Chat Completion choices is piped directly into BulletPoints.model_validate_json(). 
- **Failure Routing**: If the schema does not match perfectly, Pydantic throws a ValidationError. This instantly halts execution and routes the failure to the database's error_message column, protecting the downstream LaTeX compiler from ingesting garbage data.

---

## 7. The Jinja2 & LaTeX Compilation Engine (Implementation Next Steps)
Once the Pydantic model successfully creates memory-safe Python objects, the final payload is handed off to the PDF generation subsystem.
- **Jinja2 Templating**: A .tex file acts as the master resume skeleton. Jinja2 targets double-brace syntax within the LaTeX file and injects the extracted strings.
- **LaTeX Safety**: LaTeX uses special control characters (&, %, $, #, _, {, }, ~, ^, \\). We explicitly warn the LLM to avoid unescaped LaTeX symbols, protecting the typesetter from compilation errors.
- **Subprocess Execution**: Python's subprocess.run(['pdflatex', 'generated.tex']) will be invoked. 
- **Subprocess Isolation & Timeouts**: pdflatex compilation can sometimes enter an infinite loop if syntax is broken. The subprocess MUST be executed with a strict timeout=10 parameter. If it hangs, Python will kill the process, update the SQL state to ERROR, and move on.

---

## 8. Graceful Degradation & Error Trapping
Every external touchpoint inside the Surgeon is wrapped in a monolithic try/except block.
- Examples of trapped failures:
  - Groq API is down or rate-limited.
  - Job ID is invalid or missing.
  - Pydantic fails to unpack the JSON.
  - Subprocess LaTeX compilation times out.
- **Failure Action**: Instead of raising the error to Celery (which might crash the worker node or trigger infinite retry loops), the exception is logged to [SURGEON-ERROR], the Postgres status shifts to JobStatus.ERROR, and the traceback error string is saved to the row for developer auditing.

---

## 9. Handoff to Command Center (Phase 5)
Upon successful compilation of the PDF:
1. The PostgreSQL row is officially upgraded: job.status = JobStatus.TAILORING (and eventually READY).
2. A new payload containing the exact same job_id UUID is thrown into the sync_queue.
3. The Celery worker completes the task cleanly, immediately freeing itself to pull the next job_id from the tailor_queue.
