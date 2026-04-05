import os
from dotenv import load_dotenv
load_dotenv()
import httpx
import asyncio
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from groq import AsyncGroq
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus, UserProfile

async def assess_job_fit(job: Dict[str, Any], user_skills: str, ac: AsyncGroq) -> bool:
    """Lightweight LLM filter to check if the job matches the user's base skills."""
    if not user_skills:
        # If no skills are defined, we assume it's a match to be safe.
        return True
    
    prompt = (
        f"You are a job fit analyzer.\n"
        f"User's Base Skills: {user_skills}\n"
        f"Job Title: {job.get('title')}\n"
        f"Job Company: {job.get('company_name')}\n"
        f"Job Description Snippet: {job.get('description', '')[:1000]}\n\n"
        f"Is this job a reasonably good match for someone with the user's skills? "
        f"Answer STRICTLY with 'YES' or 'NO'."
    )
    
    try:
        response = await ac.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",  # Very fast model for this task
            temperature=0,
            max_tokens=10
        )
        content = response.choices[0].message.content.strip().upper()
        return "YES" in content
    except Exception as e:
        print(f"Error assessing job fit: {e}")
        return False

async def run_radar():
    """Fetches jobs from Remotive API and filters them based on UserProfile."""
    url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=20"
    
    db: Session = SessionLocal()
    groq_api_key = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        ac = AsyncGroq(api_key=groq_api_key)
    else:
        print("Warning: GROQ_API_KEY not found. Simple keyword matching will be skipped.")
        ac = None
    
    try:
        # Get user profile for base skills
        profile = db.query(UserProfile).first()
        base_skills = profile.base_skills if profile else ""

        print(f"Fetching remote jobs from {url}...")
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            jobs = data.get("jobs", [])[:20] # Limit to 20 jobs

        for job_data in jobs:
            job_url = job_data.get("url")
            
            # Check if job already exists in Pipeline
            existing_job = db.query(JobPipeline).filter(JobPipeline.url == job_url).first()
            if existing_job:
                continue
            
            # Simple assessment using Groq LLM if configured
            is_match = False
            if ac:
                is_match = await assess_job_fit(job_data, base_skills, ac)
            else:
                # Fallback purely checking for "remote" if no Groq API KEY (Remotive is always remote though)
                is_match = True 

            if is_match:
                print(f"Match found: {job_data.get('title')} at {job_data.get('company_name')}")
                
                # Create JobPipeline entry
                new_job = JobPipeline(
                    url=job_url,
                    company=job_data.get("company_name"),
                    title=job_data.get("title"),
                    status=JobStatus.PENDING
                )
                db.add(new_job)
                db.commit()
                db.refresh(new_job)
                
                # Kick off scrape job
                print(f"Sending Celery task for job id: {new_job.id}")
                from worker import celery_app
                celery_app.send_task('agents.scraper.scrape_job', args=[new_job.id], queue='scrape_queue')
            else:
                print(f"No match: {job_data.get('title')} at {job_data.get('company_name')}")

    except Exception as e:
        print(f"Error in run_radar: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_radar())