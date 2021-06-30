import numpy as np
import cv2
from PIL import Image, ImageOps
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
GRID_HIGHT = int(os.getenv('GRID_HIGHT'))
GRID_WIDTH = int(os.getenv('GRID_WIDTH'))

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
    desired_height = IMAGE_HIGHT  
    desired_width  = IMAGE_WIDTH           
    grid_w = GRID_WIDTH 
    grid_h = GRID_HIGHT  #std height images are (400X400) or (700X400) or (aspect_ratio_maintained_width X 400)
    ratio = (0.8,1.7)   #h/w ratio, if below lower threshold->landscape, above upper threshold->portrait, in between->square
    
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

    if(target_h/target_w  <= ratio[0]):  #if landscape image
        desired_height = desired_width
       
    hpercent = (desired_height/float(target_h))
    target_w = int((float(target_w)*float(hpercent)))
    target_h = desired_height        
        
    target_img = cv2.resize(target_img,(target_w, target_h), interpolation = cv2.INTER_CUBIC)
    self.update_state(state='PROGRESS', meta={'current': 20})

#------------------------------ Read input images from zip file and create mosaic--------------------------------------------------------
    input_imgs_path = os.path.join(temp_folder_path, "temp_zip.zip")
    archive = ZipFile(input_imgs_path, 'r')
    files = archive.namelist()
    random.shuffle(files)
    
    images_list = []     #store extracted images
    images_list_iter = 0 #list iterator
    x=0                  # width
    y=0                  # height
    i = 0                #while loop iterator
    no_image_cnt = 0     #not images file count
    n = len(files)       #images to store/shift operation

    while True:
        if i<n:     #extract from zip,blend and store in list
            if files[i].split(".")[-1] in ["png","jpg","JPG","PNG"]:   
                imgdata = archive.read(files[i])
                imgdata = io.BytesIO(imgdata)
                imgdata = Image.open(imgdata)
                imgdata = ImageOps.exif_transpose(imgdata) #ignore metadata orientation
                imgdata.thumbnail((grid_w, grid_h))
                
                if grayscale_flag:
                    imgdata = imgdata.convert('L')
                else:
                    imgdata = imgdata.convert('RGB')

                w,h = imgdata.size
                if(h/w >= ratio[1]):                                           #if portrait image
                    input_img = imgdata
                elif(h/w <= ratio[0]):                                         #if landscape image
                    input_img = imgdata.resize((grid_w,grid_h), Image.LANCZOS)
                    w,h = grid_w,grid_h
                else:                                                           #if square image
                    input_img = imgdata.resize((grid_h,grid_h), Image.LANCZOS)
                    w,h = grid_h,grid_h
                
                input_img = np.array(input_img, np.uint8)
                if grayscale_flag==False:
                    input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB)

                images_list.append(input_img)
            else: #if not a image file
                no_image_cnt +=1
                if no_image_cnt == n-1: #if zip file dosen't contain images
                    break
                i+=1
                continue    
            i+=1  
            self.update_state(state='PROGRESS', meta={'current': 20 + round(i/10)})   
        elif i==n: # shuffle images list after extraction from zip
            archive.close() 
            i+=1
            random.shuffle(images_list)
            n = n-no_image_cnt
            input_img = images_list[images_list_iter]
            h,w = input_img.shape[:2]
            images_list_iter +=1
            self.update_state(state='PROGRESS', meta={'current': 60})   
            
        else: # get the images from image list
            if images_list_iter > n-1:
                random.shuffle(images_list)
                images_list_iter = 0 
            
            input_img = images_list[images_list_iter]
            h,w = input_img.shape[:2]
            images_list_iter += 1
     
        if x+w > target_w:  # x1+x2 = w , x1 -> percent of img inside target_img frame (for edge background images)
            x1_percent = (target_w-x)/w                
            if x1_percent <= 0.3:  # very small percent is inside then ignore and leave it empty space
                x=0
                y += h
                if y >= target_h:
                    break
            else: # most percent is inside or outside then expand current img and fit to frame 
                w = target_w-x
                try: 
                    input_img = cv2.resize(input_img,(w,grid_h), interpolation = cv2.INTER_LINEAR)
                    target_img[y:y+h, x:x+w] = cv2.addWeighted(target_img[y:y+h, x:x+w],blend_factor,input_img,(1-blend_factor),0) 
                except:
                    pass
                x=0
                y += h
                if y >= target_h:
                    break 
                else:
                    continue
        try: 
            target_img[y:y+h, x:x+w] = cv2.addWeighted(target_img[y:y+h, x:x+w],blend_factor,input_img,(1-blend_factor),0)  
        except:
            pass
        x += w 
               
    
    self.update_state(state='PROGRESS', meta={'current': 80})    
#------------------------------Save the final image--------------------------------------------------------
    cv2.imwrite(os.path.join(temp_folder_path,"PhotoMosaic.jpg"),target_img) 
    self.update_state(state='PROGRESS', meta={'current': 90})    
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
