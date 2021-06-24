import numpy as np
import cv2
from PIL import Image
import os
import io 
import random
from zipfile import ZipFile
import shutil
from celery import Celery
from dotenv import load_dotenv
load_dotenv()
broker_url = os.getenv('BROKER_URL') 
backend_url = os.getenv('BACKEND_URL') 
IMAGE_HIGHT = int(os.getenv('IMAGE_HIGHT'))
IMAGE_WIDTH = int(os.getenv('IMAGE_WIDTH'))

celery_app = Celery('tasks',
             broker= broker_url,
             backend= backend_url
            )

celery_app.conf.update(
    broker_url = broker_url,
    result_backend = backend_url,
    result_persistent = False,
    accept_content = ['json'],
    task_serializer = 'json',
    task_track_started = True, 
    task_ignore_result = False
)

@celery_app.task(bind=True)
def get_mosaic(self, temp_folder_name:str, grayscale_flag: bool, focus_option:bool):

#--------------------------Set variables of program--------------------------------------------------------
    desired_height = IMAGE_HIGHT  #15
    desired_width  = IMAGE_WIDTH  #12          
    grid_size = (36,18)
    
    if focus_option:
        blend_factor = 0.8
    else:
        blend_factor = 0.7

    temp_folder_path =  os.path.join("temp", temp_folder_name)
    self.update_state(state='PROGRESS', meta={'current': 10})

#------------------------------ Read target image and calcultae the shape--------------------------------------------------------
    target_img_path = os.path.join(temp_folder_path, "target_img.jpg")
    
    if grayscale_flag:        
        target_img = cv2.imread(target_img_path,0)
        target_h,target_w = target_img.shape[:2]
    else:
        target_img = cv2.imread(target_img_path)
        target_h,target_w = target_img.shape[:2] 

    # resize_factor = 6
    # target_h,target_w = target_h*resize_factor,target_w*resize_factor
    if (target_h >= target_w):
        hpercent = (desired_height/float(target_h))
        target_w = int((float(target_w)*float(hpercent)))
        target_h = desired_height
        
        grid_h = target_h//max(grid_size)  
        grid_w = target_w//min(grid_size) 
    else:
        wpercent = (desired_width/float(target_w))
        target_h = int((float(target_h)*float(wpercent)))
        target_w = desired_width
          
        grid_w = target_w//max(grid_size)  
        grid_h = target_h//min(grid_size) 

    target_img = cv2.resize(target_img,(target_w, target_h), interpolation = cv2.INTER_CUBIC)
    self.update_state(state='PROGRESS', meta={'current': 20})

#------------------------------ Read input images from zip file --------------------------------------------------------
    input_imgs_path = os.path.join(temp_folder_path, "temp_zip.zip")
    archive = ZipFile(input_imgs_path, 'r')
    files = archive.namelist()
    random.shuffle(files)
    
    images_list = [] 
    image_list_iter = 0
    
    x=0 # width
    y=0 # height

    n_inputs = len(files)
    n_required = grid_size[0]*grid_size[1] #648 #2592
    n_store = n_required - n_inputs
    n_store = 0 if n_store < 0 else n_store
    self.update_state(state='PROGRESS', meta={'current': 40})

#------------------------------ Resize input images , store and create final img--------------------------------------------------------
    for image in files:
        if image.split(".")[-1] in ["png","jpg","JPG","PNG"]:
            imgdata = archive.read(image)
            imgdata = io.BytesIO(imgdata)
            imgdata = Image.open(imgdata)
            imgdata.thumbnail((grid_w, grid_h))
            
            if grayscale_flag:
                imgdata = imgdata.convert('L')
                input_img = imgdata.resize((grid_w,grid_h), Image.LANCZOS)
                input_img = np.array(input_img, np.uint8)                    
            else:
                imgdata = imgdata.convert('RGB')
                input_img = imgdata.resize((grid_w,grid_h), Image.LANCZOS)
                input_img = np.array(input_img, np.uint8)
                input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB)
            
            try: 
                target_img[y:y+grid_h, x:x+grid_w] = cv2.addWeighted(target_img[y:y+grid_h, x:x+grid_w],blend_factor,input_img,(1-blend_factor),0) 
            except:
                pass
          
            x += grid_w
            if x >= target_w:
                x = 0 
                y += grid_h
                
            if (image_list_iter < n_store ):
                images_list.append(input_img)
                image_list_iter += 1
                self.update_state(state='PROGRESS', meta={'current': (40 + image_list_iter/10)})
            
    archive.close()
    self.update_state(state='PROGRESS', meta={'current': 70})
#------------------------------Using stored resized images to create final img--------------------------------------------------------
    random.shuffle(images_list)
    iter = 0
    loop_condition = True
    iter_limit = len(images_list)
    while loop_condition:
          
      if (iter >= iter_limit):
        random.shuffle(images_list)
        iter = 0   

      try:
        target_img[y:y+grid_h, x:x+grid_w] = cv2.addWeighted(target_img[y:y+grid_h, x:x+grid_w],blend_factor,images_list[iter],(1-blend_factor),0) 
        iter = iter + 1
      except:
          pass
     
      x += grid_w
      if(x >= target_w):
        x = 0
        y += grid_h
        self.update_state(state='PROGRESS', meta={'current': 75+ iter/10})

      if(y >= target_h):
        loop_condition = False  
        break
    
#------------------------------Save the final image--------------------------------------------------------
    cv2.imwrite(os.path.join(temp_folder_path,"PhotoMosaic.jpg"),target_img) 

#------------------------------Delete input_imgs_zip file and target_img--------------------------------------------------------
    try:
        os.remove(target_img_path)
        os.remove(input_imgs_path)
    except :
        pass

    self.update_state(state='PROGRESS', meta={'current': 95})

#------------------------------Return temp folder name--------------------------------------------------------
    return temp_folder_name     
   
@celery_app.task  
def remove_file(temp_folder_name):
    try:
        shutil.rmtree(os.path.join("temp",temp_folder_name), ignore_errors = False)
    except :
        pass
