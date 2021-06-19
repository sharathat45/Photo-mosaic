from fastapi import FastAPI, UploadFile, Request, File, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.cloud import storage
from google.cloud import tasks_v2
from google.protobuf.timestamp_pb2 import Timestamp
from google.cloud import pubsub_v1
import json
import datetime
import os
import uuid
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
    bucket = client.get_bucket('photo-mosaic-317019-urlsigner')
        
    blob = bucket.blob(folder_name + '/target_img.jpg')
    blob.upload_from_file(target_Image.file)
    
    remove_folder_task(folder_name, countdown = int(os.getenv('CACHE_CLEAR_TIMEOUT'))*60)  
 
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
    
    client = storage.Client()
    bucket = client.get_bucket(os.getenv('BUCKET_NAME'))    
    try:
        blob = bucket.get_blob(token + '/status.txt')
        txt = str(blob.download_as_string(),'utf-8')
        status = txt.split(" ")[0]
        progress = int(txt.split(" ")[1])
    except:
        pass
    
    if status=='SUCCESS':
        blob = bucket.blob(token + '/PhotoMosaic.zip')
        blob.make_public()
    
    return {"state": status, "progress":progress }

@app.post("/start_task")
async def start_mosaic_task(background_tasks: BackgroundTasks, item: Item):  
    background_tasks.add_task(publish, item.token, item.image_option, item.focus_option)
    return {'token': item.token}

def publish(temp_folder_name:str, grayscale_flag: bool, focus_option:bool):
    topic_name = os.getenv('TOPIC_NAME')
    PROJECT_ID = os.getenv('PROJECT_NAME')
    message = { "temp_folder_name": temp_folder_name,
                "grayscale_flag":grayscale_flag, 
                "focus_option":focus_option }

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, topic_name)
    message_json = json.dumps(message)
    message_bytes = message_json.encode('utf-8')
    
    try:
        publish_future = publisher.publish(topic_path, data=message_bytes)
        publish_future.result()  # Verify the publish succeeded
        return 'Message published.'
    except Exception as e:
        print(e)

        client = storage.Client()
        bucket = client.get_bucket(os.getenv('BUCKET_NAME'))
        temp = tempfile.NamedTemporaryFile() 
        iName = "".join([str(temp.name),".txt"])
        text_file = open(iName, "w")
        txt = "ERROR 0"
        text_file.write(txt)
        text_file.close()
        blob = bucket.get_blob(temp_folder_name + '/status.txt')
        blob.upload_from_filename(iName,content_type='text/plain')
        temp.close()

        return (e, 500)
    
def remove_folder_task(folder_name,countdown):
    # client = tasks_v2.CloudTasksClient()   
    client = tasks_v2.CloudTasksClient.from_service_account_json('service_account.json')
    project = os.getenv('PROJECT_NAME')
    queue = os.getenv('QUEUE_NAME') 
    location = os.getenv('QUEUE_LOCATION') 
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
    bucket_name = os.getenv('BUCKET_NAME')
    try:
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=token)
        for blob in blobs:
            blob.delete()
    except :
        pass

    return {"token": token}    
