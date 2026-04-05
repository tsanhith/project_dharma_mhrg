import uuid
from database.db import SessionLocal
from database.models import JobPipeline, JobStatus

def insert_test_job(url: str):
    db = SessionLocal()
    
    job_id = str(uuid.uuid4())
    test_job = JobPipeline(
        id=job_id,
        url=url,
        company="Test Company",
        title="Software Engineer",
        status=JobStatus.PENDING
    )
    
    db.add(test_job)
    db.commit()
    print(f"Inserted job {job_id} for URL: {url}")
    
    # Trigger the task
    from worker import celery_app
    celery_app.send_task("agents.scraper.scrape_job", kwargs={"job_id": job_id}, queue="scrape_queue")
    print(f"Sent task to scrape_queue for job {job_id}")

if __name__ == "__main__":
    import time
    insert_test_job(f"https://en.wikipedia.org/wiki/Python_(programming_language)?t={time.time()}")
