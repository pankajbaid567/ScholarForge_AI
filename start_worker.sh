#!/bin/sh
# Start Celery worker in the background
celery -A src.workers.celery_app worker --loglevel=info --pool=solo -Q ingestion,evaluation &

# Start a dummy HTTP server in the foreground so Render Web Service healthchecks pass
python -m http.server $PORT
