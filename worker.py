import os
import asyncio
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

import agents.radar
import agents.secretary

load_dotenv()

# Use Redis running on localhost by default for local development
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "dharma_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["agents.tailor", "agents.notion_sync", "agents.scraper", "agents.applier"]
)

# Force the worker to route tasks to their specific queues
celery_app.conf.task_routes = {
    'agents.scraper.*': {'queue': 'scrape_queue'},
    'agents.tailor.*': {'queue': 'tailor_queue'},
    'agents.notion_sync.*': {'queue': 'sync_queue'},
    'agents.applier.*': {'queue': 'apply_queue'},
    'worker.test_connection': {'queue': 'scrape_queue'},
    'worker.execute_radar': {'queue': 'scrape_queue'},
    'worker.execute_secretary': {'queue': 'scrape_queue'}
}

# Celery Beat Schedule
celery_app.conf.beat_schedule = {
    'run-radar-every-4-hours': {
        'task': 'worker.execute_radar',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    'run-secretary-daily': {
        'task': 'worker.execute_secretary',
        'schedule': crontab(minute=0, hour='0,12'), 
    }
}

@celery_app.task(name='worker.execute_radar')
def execute_radar():
    print("[WORKER] Running scheduled radar execution...")
    asyncio.run(agents.radar.run_radar())
    return "Radar execution complete."

@celery_app.task(name='worker.execute_secretary')
def execute_secretary():
    print("[WORKER] Running scheduled secretary execution...")
    agents.secretary.run_secretary()
    return "Secretary execution complete."

# Example test task to verify the worker is listening
@celery_app.task(name='worker.test_connection')
def test_connection(message: str):
    print(f"[WORKER PING] Received message: {message}")
    return f"Ping successful: {message}"
