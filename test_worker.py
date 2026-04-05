from worker import celery_app
import time

print("Sending a test message to the broker...")
# Send the task to scrape_queue
task = celery_app.send_task('worker.test_connection', args=['Hello, Project Dharma!'])
print(f"Task dispatched with ID: {task.id}")

# Wait for result
print("Waiting for worker completion...")
try:
    result = task.get(timeout=5)
    print(f"Success! Result: {result}")
except Exception as e:
    print(f"Task Failed or Timed Out (is your worker and Redis running?): {e}")
