from database.db import SessionLocal
from database.models import JobPipeline, JobStatus
from worker import celery_app

db = SessionLocal()

# 1. Create a dummy PENDING job in Postgres
new_job = JobPipeline(
    url="https://example.com",
    company="Example Corp",
    title="Test Job",
    status=JobStatus.PENDING
)
db.add(new_job)
db.commit()
db.refresh(new_job)

print(f"Created fake job to test: {new_job.id}")

# 2. Push it to the Scraper Queue!
task = celery_app.send_task('agents.scraper.scrape_job', args=[new_job.id], queue='scrape_queue')
print("Pinged Scout! Check the worker logs!")
