import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from celery import shared_task
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus
from worker import celery_app

async def async_scrape_url(url: str) -> str:
    """Navigates to URL and extracts the body text, cleaning junk HTML"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Some remote sites like Jobicy sit on network connections forever, breaking 'networkidle'
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        
        # Give it a couple of seconds to settle JS if any
        await page.wait_for_timeout(3000)

        # Inject JavaScript to strip out noisy elements (navs, footers, scripts) before grabbing text
        await page.evaluate("""
            document.querySelectorAll('nav, header, footer, aside, script, style, form, noscript, [role="navigation"], [role="banner"], [role="contentinfo"]').forEach(el => el.remove());
        """)

        # Extract all text from the body using Playwright's visual rendering (preserves layout)
        raw_text = await page.locator("body").inner_text()
        
        await browser.close()
        return raw_text

@celery_app.task(name='agents.scraper.scrape_job', bind=True)
def scrape_job(self, job_id: str):
    """The Scout: Grabs the job_id, looks up the URL, scrapes it, and queues the Tailor"""
    print(f"[SCOUT] Initiating scrape for Job ID: {job_id}")
    db = SessionLocal()
    
    try:
        # 1. Look up the job
        job = db.query(JobPipeline).filter(JobPipeline.id == job_id).first()
        if not job:
            raise ValueError(f"Job ID {job_id} not found in database.")
            
        if job.status != JobStatus.PENDING:
            print(f"[SCOUT] Job {job_id} is not PENDING. Skipping.")
            return
            
        # 2. Scrape the text
        print(f"[SCOUT] Navigating to {job.url}...")
        raw_text = asyncio.run(async_scrape_url(job.url))
        
        # 3. Update Database (Success)
        job.raw_jd_text = raw_text
        job.status = JobStatus.SCRAPED
        db.commit()
        print(f"[SCOUT] Successfully scraped. Updated DB state to SCRAPED.")
        
        # 4. Pass the ticket to the next Robot (The Surgeon / Tailor)
        print(f"[SCOUT] Pushing job to Tailor Queue...")
        celery_app.send_task('agents.tailor.tailor_resume', args=[job_id], queue='tailor_queue')

    except Exception as e:
        # Graceful Degradation: Do not crash! Log it and fail the DB row.
        print(f"[SCOUT-ERROR] Failed to scrape {job_id}: {str(e)}")
        if 'job' in locals() and job:
            job.status = JobStatus.ERROR
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
