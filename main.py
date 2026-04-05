import uuid
import os
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus, UserProfile
from worker import celery_app
from agents.searcher_stream import hunt_stream

app = FastAPI(title="Project Dharma Command Center")

# Create PDFs folder if missing and mount it strictly for browser viewing
os.makedirs("output_pdfs", exist_ok=True)
app.mount("/pdfs", StaticFiles(directory="output_pdfs"), name="pdfs")

# Use slightly different jinja syntax if needed to completely separate from resume templates, 
# but FastAPI's default Jinja2Templates handles standard {{ }} syntax perfectly.
templates = Jinja2Templates(directory="templates/frontend")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    db = SessionLocal()
    # Fetch recent jobs to display
    jobs = db.query(JobPipeline).order_by(JobPipeline.status.desc()).limit(20).all()
    db.close()
    return templates.TemplateResponse(request, "index.html", {"jobs": jobs})    

@app.get("/pipeline", response_class=HTMLResponse)
async def view_pipeline(request: Request):
    db = SessionLocal()
    jobs = db.query(JobPipeline).order_by(JobPipeline.status.desc()).all()
    db.close()
    return templates.TemplateResponse(request, "pipeline.html", {"jobs": jobs})

@app.get("/brain", response_class=HTMLResponse)
async def view_brain(request: Request):
    db = SessionLocal()
    profile = db.query(UserProfile).first()
    db.close()
    return templates.TemplateResponse(request, "brain.html", {"profile": profile})

@app.post("/submit_job")
async def submit_job(
    request: Request,
    url: str = Form(...),
    company: str = Form(""),
    title: str = Form("")
):
    db = SessionLocal()
    job_id = str(uuid.uuid4())
    
    # Optional URL clean logic:
    # If the exact URL already exists, database constraint might crash unless we handle it
    # We will try/except and append a short UUID/time to duplicate tests, or just notify user.
    
    try:
        new_job = JobPipeline(
            id=job_id,
            url=url,
            company=company if company else "Unknown",
            title=title if title else "Applicant",
            status=JobStatus.PENDING
        )
        db.add(new_job)
        db.commit()
        
        # Trigger Celery Pipeline
        celery_app.send_task("agents.scraper.scrape_job", kwargs={"job_id": job_id}, queue="scrape_queue")
        
    except Exception as e:
        db.rollback()
        # You could return an error template, but for now we'll just ignore or log
        print(f"Error inserting job: {e}")
    finally:
        db.close()
        
    return RedirectResponse(url="/", status_code=303)

@app.get("/api/jobs")
def get_jobs_api():
    """Returns JSON of current jobs so frontend can auto-refresh"""
    db = SessionLocal()
    jobs = db.query(JobPipeline).all()
    db.close()
    return [{"id": j.id, "company": j.company, "title": j.title, "url": j.url, "status": j.status.name} for j in jobs]

@app.get("/api/profile")
def get_profile_api():
    db = SessionLocal()
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)
    
    result = {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "linkedin_url": profile.linkedin_url or "",
        "github_url": profile.github_url or "",
        "portfolio_url": profile.portfolio_url or "",
        "base_skills": profile.base_skills or "",
        "base_resume_text": profile.base_resume_text or ""
    }
    db.close()
    return result

@app.post("/api/profile")
async def update_profile_api(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    location: str = Form(...),
    linkedin_url: str = Form(""),
    github_url: str = Form(""),
    portfolio_url: str = Form(""),
    base_skills: str = Form(""),
    base_resume_text: str = Form("")
):
    db = SessionLocal()
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile()
        db.add(profile)
    
    profile.name = name
    profile.email = email
    profile.phone = phone
    profile.location = location
    profile.linkedin_url = linkedin_url
    profile.github_url = github_url
    profile.portfolio_url = portfolio_url
    profile.base_skills = base_skills
    profile.base_resume_text = base_resume_text
    
    db.commit()
    db.close()
    return RedirectResponse(url="/brain", status_code=303)

@app.post("/api/jobs/{job_id}/apply")
async def trigger_apply_job(job_id: str):
    """Triggers the headed Applier agent for a READY job."""
    db = SessionLocal()
    job = db.query(JobPipeline).filter(JobPipeline.id == job_id).first()
    if job:
        if job.status == JobStatus.READY:
            # Trigger Celery Applier Pipeline
            celery_app.send_task("agents.applier.apply_job", kwargs={"job_id": job_id}, queue="apply_queue")
        elif job.status == JobStatus.PENDING or job.status == JobStatus.ERROR:
            # Force trigger the scraper if they click apply early
            celery_app.send_task("agents.scraper.scrape_job", args=[job.id], queue="scrape_queue")
    db.close()
    return RedirectResponse(url="/", status_code=303)
@app.post("/api/hunt")
async def trigger_ai_hunt(background_tasks: BackgroundTasks):
    """Triggers the AI Hunter stream logic indirectly if needed, or deprecate."""
    # background_tasks.add_task(hunt_stream) # Handled by the SSE route now
@app.post("/api/purge")
async def trigger_purge():
    "Wipes the database to allow fresh hunts for testing."
    db = SessionLocal()
    db.query(JobPipeline).delete()
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/hunt/stream")
async def stream_ai_hunt():
    return StreamingResponse(hunt_stream(), media_type="text/event-stream")

