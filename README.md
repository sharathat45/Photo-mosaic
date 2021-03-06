# Photo mosaic web

![image](https://user-images.githubusercontent.com/46818446/143681621-758939ad-a3d8-46ec-b9bd-3e53d255abbe.png)

[Photo Mosaic Website](https://photo-mosaic-317019.an.r.appspot.com/)

[Download executable application](https://photo-mosaic-317019.an.r.appspot.com/)

Install dependencies:
```
pip install -r requirements.txt
```

## Fastapi Server 
Start fast api server by running:
```
uvicorn server:app 
```
 or 
```
gunicorn -w 4 -k uvicorn.workers.UvicornWorker server:app
```
access webpage at:  http://127.0.0.1:8000

## Start Redis instance
## Celery worker 
Start Celery worker by running:
```
celery -A mosaic worker --pool=solo --loglevel=INFO
```
checkout gcp app in [other branch](https://github.com/sharathat45/Photo-mosaic/tree/Photo_mosaic_gcp_app_engine) 
<br>
Deployed website @ [Photo Mosaic](https://photo-mosaic-317019.an.r.appspot.com/)
