import os
import asyncio
from playwright.async_api import async_playwright
from celery import shared_task
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus, UserProfile

async def async_apply_to_job(job_id: str):
    db = SessionLocal()
    job = db.query(JobPipeline).filter(JobPipeline.id == job_id).first()
    if not job:
        print(f"[APPLIER] Job {job_id} not found.")
        return

    profile = db.query(UserProfile).first()
    if not profile:
        print("[APPLIER] User profile not found. Cannot autofill.")
        return

    # Find the PDF
    public_dir = os.path.expanduser(r"~\Documents\Ready_Resumes")
    safe_company = "".join(c for c in (job.company or "Unknown") if c.isalnum() or c in " _-").strip()
    safe_title = "".join(c for c in (job.title or "Role") if c.isalnum() or c in " _-").strip()
    final_pdf_name = f"Resume_{safe_company}_{safe_title}.pdf".replace(" ", "_")
    pdf_path = os.path.join(public_dir, final_pdf_name)

    if not os.path.exists(pdf_path):
        pdf_path = os.path.abspath(f"output_pdfs/resume_{job_id}.pdf")

    print(f"[APPLIER] Opening {job.url} with {pdf_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(job.url)
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            print(f"[APPLIER] Could not fully load page or network idle timeout: {e}")

        # Basic Heuristics for auto-filling
        print("[APPLIER] Attempting heuristic auto-fill...")
        try:
            # Name
            name_inputs = page.locator("input[name*='name' i], input[id*='name' i]")
            if await name_inputs.count() > 0:
                await name_inputs.first.fill(profile.name, timeout=2000)
            
            # Email
            email_inputs = page.locator("input[type='email'], input[name*='email' i], input[id*='email' i]")
            if await email_inputs.count() > 0:
                await email_inputs.first.fill(profile.email, timeout=2000)
                
            # Phone
            if profile.phone:
                phone_inputs = page.locator("input[type='tel'], input[name*='phone' i], input[id*='phone' i]")
                if await phone_inputs.count() > 0:
                    await phone_inputs.first.fill(profile.phone, timeout=2000)
                    
            # LinkedIn
            if profile.linkedin_url:
                linkedin_inputs = page.locator("input[name*='linkedin' i], input[id*='linkedin' i], input[placeholder*='linkedin' i]")
                if await linkedin_inputs.count() > 0:
                    await linkedin_inputs.first.fill(profile.linkedin_url, timeout=2000)
                    
            # GitHub
            if profile.github_url:
                github_inputs = page.locator("input[name*='github' i], input[id*='github' i], input[placeholder*='github' i]")
                if await github_inputs.count() > 0:
                    await github_inputs.first.fill(profile.github_url, timeout=2000)
                    
            # Resume
            if os.path.exists(pdf_path):
                file_input = page.locator("input[type='file'][name*='resume' i], input[type='file'][id*='resume' i], input[type='file']")
                if await file_input.count() > 0:
                    await file_input.first.set_input_files(pdf_path, timeout=2000)
                    
        except Exception as e:
            print(f"[APPLIER] Heuristic fill exception: {e}. Moving on to pause.")

        print("\n" + "="*50)
        print("[APPLIER] PAUSING! A Playwright Inspector window should appear.")
        print("[APPLIER] Fill out custom fields, solve CAPTCHAs, and click Submit.")
        print("[APPLIER] Once finished, click 'Resume' in the Inspector or close the browser.")
        print("="*50 + "\n")
        
        await page.pause()

        # Update Job Status upon completion
        job.status = JobStatus.APPLIED
        db.commit()
        print(f"[APPLIER] Job {job_id} marked as APPLIED.")
        
        await browser.close()

from worker import celery_app

@celery_app.task(name='agents.applier.apply_job')
def apply_job(job_id: str):
    """Celery task entry point to trigger the applier agent."""
    # Note: async_playwright needs to run in its own event loop since Celery is sync
    asyncio.run(async_apply_to_job(job_id))
    return f"Applier completed for {job_id}"
