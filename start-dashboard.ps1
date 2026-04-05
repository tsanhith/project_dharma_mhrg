echo "Starting Project Dharma Command Center Pipeline..."

echo "1. Starting Celery Worker in the background..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .\venv\Scripts\Activate; celery -A worker.celery_app worker -Q queue,scrape_queue,tailor_queue,sync_queue --pool=solo --loglevel=info"

echo "2. Starting FastAPI Dashboard UI..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .\venv\Scripts\Activate; uvicorn main:app --reload --port 8000"

echo "Dashboard is starting up!"
echo "Please wait 5 seconds and open your browser to: http://127.0.0.1:8000"
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:8000"
