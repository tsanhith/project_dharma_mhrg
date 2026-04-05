import os
import requests
from celery import shared_task
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus
from worker import celery_app

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

@celery_app.task(name='agents.notion_sync.sync_to_notion', bind=True)
def sync_to_notion(self, job_id: str):
    """The Command Center: Synchronizes the successfully tailored resume directly into a Notion Database."""
    print(f"[NOTION] Initiating sync for Job ID: {job_id}")
    db = SessionLocal()
    
    try:
        # 1. Fetch Job from DB
        job = db.query(JobPipeline).filter(JobPipeline.id == job_id).first()
        if not job or job.status != JobStatus.TAILORING:
            print(f"[NOTION] Job {job_id} is not TAILORING or not found. Skipping.")
            return

        if not NOTION_API_KEY or not NOTION_DATABASE_ID:
            raise ValueError("NOTION_API_KEY or NOTION_DATABASE_ID is missing from .env.")

        title_text = f"{job.title} @ {job.company}" if job.company else f"{job.title}"
        print(f"[NOTION] Pushing to Notion Database for {title_text}...")

        # 2. Prepare Notion API Payload
        url = "https://api.notion.com/v1/pages"
        headers = {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

        # Setup public document storage so the user can easily find the Resumes
        import shutil
        public_dir = os.path.expanduser(r"~\Documents\Ready_Resumes")
        os.makedirs(public_dir, exist_ok=True)

        safe_company = "".join(c for c in (job.company or "Unknown") if c.isalnum() or c in " _-").strip()
        safe_title = "".join(c for c in (job.title or "Role") if c.isalnum() or c in " _-").strip()
        final_pdf_name = f"Resume_{safe_company}_{safe_title}.pdf".replace(" ", "_")
        final_pdf_path = os.path.join(public_dir, final_pdf_name)

        old_pdf_path = os.path.abspath(f"output_pdfs/resume_{job_id}.pdf")
        
        # Move the backend tmp file to the easy-to-read location
        if os.path.exists(old_pdf_path):
            shutil.copy(old_pdf_path, final_pdf_path)
            display_path = final_pdf_path
        else:
            display_path = old_pdf_path # Fallback just in case

        data = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Role / Title": {
                    "title": [
                        {
                            "text": {
                                "content": title_text
                            }
                        }
                    ]
                },
                "Company": {
                    "rich_text": [
                        {
                            "text": {
                                "content": job.company or "Unknown"
                            }
                        }
                    ]
                },
                "Job URL": {
                    "url": job.url
                },
                "Status": {
                    "status": {
                        "name": "Ready to Apply"
                    }
                },
                "Local PDF Path": {
                    "rich_text": [
                        {
                            "text": {
                                "content": display_path
                            }
                        }
                    ]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "Raw Job Description"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": (job.raw_jd_text[:1900] + '...') if job.raw_jd_text and len(job.raw_jd_text) > 1900 else (job.raw_jd_text or "No description provided.")}}]
                    }
                }
            ]
        }

        # 3. Fire to Notion
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            raise Exception(f"Notion API Error: {response.text}")

        # 4. Database Update (Success)
        job.status = JobStatus.READY
        db.commit()
        print(f"[NOTION] Successfully synced {job_id} to Notion Command Center!")

    except Exception as e:
        print(f"[NOTION-ERROR] Failed to sync {job_id}: {str(e)}")
        if 'job' in locals() and job:
            job.status = JobStatus.ERROR
            job.error_message = f"Notion Sync failed: {str(e)}"
            db.commit()
    finally:
        db.close()
