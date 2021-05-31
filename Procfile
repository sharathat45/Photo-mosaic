web: gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app
worker: celery -A mosaic worker --pool=solo 
