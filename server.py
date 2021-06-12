from fastapi import FastAPI, UploadFile, Request, File, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from google.cloud import storage

from google.cloud import tasks_v2
import json

from datetime import timedelta
from mosaic import *
import os
import shutil
import uuid

    
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

class Item(BaseModel):
    token: str
    image_option: bool
    focus_option: bool   

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "photo-mosaic-315612-abb495931ce6.json"

@app.get('/')
def home(request: Request):    
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload_files")
async def get_target_image(target_Image:UploadFile = File(...)):
    folder_name =  str(uuid.uuid4())
    client = storage.Client()
    bucket = client.get_bucket('temp_files_mosaic')
        
    blob = bucket.blob(folder_name + '/target_img.jpg')
    blob.upload_from_file(target_Image.file)
    
    blob = bucket.blob(folder_name + '/temp_zip.zip')
    signed_url = blob.generate_signed_url(expiration= timedelta(minutes=5), method="PUT", version="v4") 

    temp = tempfile.NamedTemporaryFile() 
    iName = "".join([str(temp.name),".txt"])
    text_file = open(iName, "w")
    text_file.write('STARTED 10')
    text_file.close()
    blob = bucket.blob(folder_name +'/status.txt')
    blob.upload_from_filename(iName,content_type='text/plain')
    temp.close()

    # remove_file.apply_async(["Untitled"],countdown=5*60)  #5 mins
    return {"SignedUrl": signed_url, "token": folder_name} 
    
@app.get('/api/status/{token}')
async def status(token):
    status = "STARTED"
    progress = 0
    try:
        client = storage.Client()
        bucket = client.get_bucket('temp_files_mosaic')
        blob = bucket.get_blob(token + '/status.txt')
        txt = str(blob.download_as_string(),'utf-8')
        status = txt.split(" ")[0]
        progress = int(txt.split(" ")[1])
    except:
        pass    
    return {"state": status, "progress":progress }
    
@app.get('/api/download_final_image/{token}')
async def download_final_image(token):
    client = storage.Client()
    bucket = client.get_bucket('temp_files_mosaic')
    
    object_bytes = 0
    for blobs in bucket.list_blobs(prefix=token):
            if str(blobs).find("PhotoMosaic") != -1 : 
                object_bytes = io.BytesIO(blobs.download_as_string())
                break
    return StreamingResponse(object_bytes, media_type="images/jpeg")

@app.post("/start_task")
async def start_mosaic_task(background_tasks: BackgroundTasks, item: Item):  
    BCKGND_TASK = False
    if BCKGND_TASK == True:
        background_tasks.add_task(get_mosaic, item.token, item.image_option, item.focus_option)
    else: 
        client = tasks_v2.CloudTasksClient()
        
        project = 'photo-mosaic-315612'
        queue = 'MosaicQueue'
        location = 'asia-south1'
        payload = { 'token':  item.token,
                    'image_option': item.image_option,
                    'focus_option': item.focus_option      }
        payload = json.dumps(payload)
        converted_payload = payload.encode()

        parent = client.queue_path(project, location, queue)
        task = {
                'app_engine_http_request': {  
                    'http_method': tasks_v2.HttpMethod.POST,
                    'relative_uri': '/example_task_handler'
                }
        }
        task["app_engine_http_request"]["headers"] = {"Content-type": "application/json"}
        task['app_engine_http_request']['body'] = converted_payload
        response = client.create_task(parent=parent, task=task)
        print(response)

    return {"token": item.token}

@app.post("/example_task_handler")
async def gcs_push_task(item: Item):
    get_mosaic(item.token, item.image_option, item.focus_option)
    return {"token": item.token}