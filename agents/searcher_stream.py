import os
import sys
import requests
import json
import time
import subprocess
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus, UserProfile
from typing import List, Dict
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def get_search_keywords() -> List[str]:
    db = SessionLocal()
    profile = db.query(UserProfile).first()
    db.close()
    if not profile or not profile.base_skills:
        return ["Software", "Engineer"]
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = f"Given these skills: {profile.base_skills}\nWhat are the two most relevant job title keywords (e.g. 'Data', 'Scientist', 'Python', 'React') to search for? Respond with JUST comma separated words, no quotes."
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=15
        )
        raw_output = response.choices[0].message.content.strip()
        keywords = [k.strip() for k in raw_output.replace('"', '').split(',')]  
        return keywords
    except:
        return ["Software", "Developer"]

def fetch_jobicy_jobs() -> List[Dict]:
    jobs = []
    industries = ['engineering', 'programming', 'data-science']
    for ind in industries:
        url = f"https://jobicy.com/api/v2/remote-jobs?count=50&industry={ind}"  
        try:
            response = requests.get(url, timeout=15)
            data = response.json()
            fetched = data.get('jobs', [])
            for j in fetched:
                jobs.append({
                    'url': j.get('url'),
                    'title': j.get('jobTitle'),
                    'companyName': j.get('companyName'),
                    'source': 'Jobicy'
                })
        except Exception:
            pass
    return jobs

def fetch_multi_portal_jobs(query: str) -> List[Dict]:
    try:
        script_path = os.path.join(os.path.dirname(__file__), 'multi_portal_search.py')
        result = subprocess.run(
            [sys.executable, script_path, query],
            capture_output=True, text=True, timeout=60
        )
        # Parse JSON from stdout (ignoring any other print statements)
        for line in result.stdout.strip().split('\n')[::-1]:
            try:
                return json.loads(line)
            except:
                pass
        return []
    except Exception as e:
        print(f"Subprocess fetch failed: {e}")
        return []

def hunt_stream():
    """Generator that yields SSE logs for the frontend."""
    yield f"data: {json.dumps({'message': '[HUNTER] Initializing...' })}\n\n"
    db = SessionLocal()
    
    yield f"data: {json.dumps({'message': '[HUNTER] Analyzing AI target keywords...' })}\n\n"
    keywords = get_search_keywords()

    broad_keywords = []
    for k in keywords:
        broad_keywords.extend(k.replace('Engineer', '').replace('Developer', '').split())
    broad_keywords = [b.lower() for b in broad_keywords if b.strip()]

    msg = f"[HUNTER] Extracted AI Target Keywords: {broad_keywords}"
    print(msg)
    yield f"data: {json.dumps({'message': msg })}\n\n"

    yield f"data: {json.dumps({'message': '[HUNTER] Accessing public Remote Job Boards (Jobicy API)...' })}\n\n"
    jobicy_jobs = fetch_jobicy_jobs()

    yield f"data: {json.dumps({'message': '[HUNTER] Deep diving into LinkedIn, Indeed, and Remotive...' })}\n\n"
    search_query = " ".join(broad_keywords[:3]) + " Remote"
    multi_jobs = fetch_multi_portal_jobs(search_query)

    all_jobs = jobicy_jobs + multi_jobs
    if not all_jobs:
        yield f"data: {json.dumps({'message': '[HUNTER] API issue, no jobs found.' })}\n\n"
        yield "data: {\"done\": true}\n\n"
        db.close()
        return

    msg = f"[HUNTER] Downloaded {len(all_jobs)} global tech remote jobs to filter."
    print(msg)
    yield f"data: {json.dumps({'message': msg })}\n\n"
    yield f"data: {json.dumps({'message': '[HUNTER] Filtering market against your specific profile...' })}\n\n"

    matched_jobs = []
    for job in all_jobs:
        job_title_lower = str(job.get('title', '')).lower()
        job_source = str(job.get('source', '')).lower()
        combined_text = job_title_lower + " " + job_source
        # Add slight broad match fallback if not from strict API
        if any(kw in combined_text for kw in broad_keywords) or 'linkedin' in job_source or 'indeed' in job_source:
            matched_jobs.append(job)

    # Let's take more if from diverse sources
    matched_jobs = matched_jobs[:15] 

    msg = f"[HUNTER] Discovered {len(matched_jobs)} highly relevant jobs matching your profile!"
    print(msg)
    yield f"data: {json.dumps({'message': msg })}\n\n"

    added_jobs = []
    added_count = 0
    for job in matched_jobs:
        link = job.get('url')
        if not link: continue
        existing = db.query(JobPipeline).filter(JobPipeline.url == link).first()
        if not existing:
            new_job = JobPipeline(
                url=link,
                company=job.get('companyName', 'Unknown'),
                title=job.get('title', 'Unknown'),
                status=JobStatus.PENDING
            )
            db.add(new_job)
            added_jobs.append(new_job)
            added_count += 1
            yield f"data: {json.dumps({'message': f'[HUNTER] Injecting -> {new_job.title} at {new_job.company}' })}\n\n"

    db.commit()

    msg = f"[HUNTER] Successfully injected {added_count} new targeted remote jobs directly into your Radar UI!"
    print(msg)
    yield f"data: {json.dumps({'message': msg })}\n\n"

    if added_count > 0:
        yield f"data: {json.dumps({'message': '[HUNTER] Handing off the URLs to Scout to scrape the raw descriptions...' })}\n\n"
        from worker import celery_app
        for job in added_jobs:
            celery_app.send_task("agents.scraper.scrape_job", args=[job.id], queue="scrape_queue")

    db.close()
    time.sleep(1.0)
    yield "data: {\"done\": true}\n\n"
