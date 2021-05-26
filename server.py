from fastapi import FastAPI, UploadFile, Request, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import uvicorn

import os
import shutil
import uuid

from mosaic import *
from celery.result import AsyncResult

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

@app.post("/api/v1/upload_files/")
async def get_target_image( target_Image: UploadFile = File(...), input_Images:UploadFile = File(...)):
    folder_name =  str(uuid.uuid4())
    folder_path = os.path.join("temp", folder_name)
    os.mkdir(folder_path)
    target_image = os.path.join(folder_path, "target_img.jpg")
    input_images = os.path.join(folder_path, "temp_zip.zip")

    remove_file.apply_async([folder_name],countdown=5*60)  #5 mins
    
    with open(target_image, "wb") as buffer:
        shutil.copyfileobj(target_Image.file, buffer)

    with open(input_images, "wb") as buffer:    
        shutil.copyfileobj(input_Images.file, buffer)
   
    return {"token": folder_name}

@app.post("/api/v1/start_task/")
async def get_target_image( item: Item):
    print(item.token, item.image_option, item.focus_option)
    r =  get_mosaic.delay(item.token, item.image_option, item.focus_option)
    return {"token": r.id}

@app.get('/api/v1/search_final_image/{token}')
async def search_final_image(token):
    process = AsyncResult(token)
    
    try:
        progress = process.info.get('current',0)
    except:
        progress = 0    

    return {"state": process.status, "progress":progress }
    

@app.get('/api/v1/download_final_image/{token}')
async def download_final_image(token):
    process = AsyncResult(token)
    folder = process.result
    file_path = os.path.join("temp", folder, "PhotoMosaic.jpg")
    return FileResponse(file_path)
 



