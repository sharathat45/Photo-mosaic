from fastapi import FastAPI, UploadFile, Request, File, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from google.cloud import storage
from google.cloud import tasks_v2
from google.protobuf.timestamp_pb2 import Timestamp
from mosaic_2 import get_mosaic
import json
import datetime
import os
import shutil
import uuid
import io
import tempfile

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

class Item(BaseModel):
    token: str
    image_option: bool
    focus_option: bool   

@app.get('/')
def home(request: Request):   
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload_files")
async def get_target_image(target_Image:UploadFile = File(...)):
    folder_name =  str(uuid.uuid4())
    client = storage.Client()
    bucket = client.get_bucket(os.getenv('BUCKET_NAME',"temp_files_mosaic"))
        
    blob = bucket.blob(folder_name + '/target_img.jpg')
    blob.upload_from_file(target_Image.file)
    
    remove_folder_task(folder_name,countdown=8*60)  #8 mins
 
    blob = bucket.blob(folder_name + '/temp_zip.zip')
    signed_url = blob.generate_signed_url(expiration= datetime.timedelta(minutes=5), method="PUT", version="v4") 

    temp = tempfile.NamedTemporaryFile() 
    iName = "".join([str(temp.name),".txt"])
    text_file = open(iName, "w")
    text_file.write('STARTED 10')
    text_file.close()
    blob = bucket.blob(folder_name +'/status.txt')
    blob.upload_from_filename(iName,content_type='text/plain')
    temp.close()

    return {"SignedUrl": signed_url, "token": folder_name} 
    
@app.get('/api/status/{token}')
async def status(token):
    status = "STARTED"
    progress = 0
    try:
        client = storage.Client()
        bucket = client.get_bucket(os.getenv('BUCKET_NAME',"temp_files_mosaic"))
        blob = bucket.get_blob(token + '/status.txt')
        txt = str(blob.download_as_string(),'utf-8')
        status = txt.split(" ")[0]
        progress = int(txt.split(" ")[1])
    except:
        pass    
    return {"state": status, "progress":progress }

@app.post("/start_task")
async def start_mosaic_task(background_tasks: BackgroundTasks, item: Item):  
    BCKGND_TASK = True
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
                    'relative_uri': '/mosaic_task_handler'
                }
        }
        task["app_engine_http_request"]["headers"] = {"Content-type": "application/json"}
        task['app_engine_http_request']['body'] = converted_payload
        response = client.create_task(parent=parent, task=task)
        print(response)

    return {"token": item.token}

@app.post("/mosaic_task_handler")
async def mosaic_task_handler(item: Item):
    get_mosaic(item.token, item.image_option, item.focus_option)
    return {"token": item.token}

def remove_folder_task(folder_name,countdown):
    client = tasks_v2.CloudTasksClient()     
    project = 'photo-mosaic-315612'
    queue = 'MosaicQueue'
    location = 'asia-south1'
    parent = client.queue_path(project, location, queue)
    task = {
            'app_engine_http_request': {  
                'http_method': tasks_v2.HttpMethod.GET,
                'relative_uri': '/remove_folder_task_handler/'+ folder_name
            }
    }
    timestamp = (datetime.datetime.utcnow() + datetime.timedelta(seconds=countdown)).timestamp()
    seconds = int(timestamp)
    nanos = int(timestamp % 1 * 1e9)
    proto_timestamp = Timestamp(seconds=seconds, nanos=nanos)
    task['schedule_time'] = proto_timestamp
    client.create_task(parent=parent, task=task)
  
@app.get("/remove_folder_task_handler/{token}")
async def remove_folder_task_handler(token:str):
    bucket_name = os.getenv('BUCKET_NAME',"temp_files_mosaic")
    try:
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=token)
        for blob in blobs:
            blob.delete()
    except :
        pass

    return {"token": token}    
