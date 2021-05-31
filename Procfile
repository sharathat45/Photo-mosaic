web: gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app
worker: celery worker --app=mosaic.celery_app
