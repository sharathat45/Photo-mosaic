web: uvicorn server:app --host=0.0.0.0 --port=${PORT:-8000}
web: celery -A mosaic worker --pool=solo
web: service redis-server start
