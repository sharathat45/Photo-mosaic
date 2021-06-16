from PIL import Image
from zipfile import ZipFile,ZIP_DEFLATED
from google.cloud import storage
import numpy as np
import cv2
import os
import io 
import random
import tempfile
import base64
import json

def get_mosaic(event, context):
    # print("""This Function was triggered by messageId {} published at {} to {} """.format(context.event_id, context.timestamp, context.resource["name"]))
    
    temp_folder_name = 0
    try:
        if 'data' in event:
            data = base64.b64decode(event['data'])
            data = json.loads(data.decode())
            temp_folder_name = data['temp_folder_name']
            grayscale_flag = data['grayscale_flag']
            focus_option = data['focus_option'] 
            
            mosaic_task(temp_folder_name, grayscale_flag, focus_option)
        else:
            update_state(temp_folder_name,"ERROR",meta = {'current': 0})
            print("Failed input data format....................")    
    except Exception as e:
        update_state(temp_folder_name,"ERROR",meta = {'current': 0})
        print(e)   
        print("ERROR:Internal error....................")   
        
    return temp_folder_name


def update_state(token,state, meta):
    client = storage.Client()
    bucket = client.get_bucket(os.getenv('BUCKET_NAME'))
    print(state,meta['current'])
    try:
        temp = tempfile.NamedTemporaryFile() 
        iName = "".join([str(temp.name),".txt"])
        text_file = open(iName, "w")
        txt = state + " " + str(meta['current'])
        text_file.write(txt)
        text_file.close()
        blob = bucket.get_blob(token + '/status.txt')
        blob.upload_from_filename(iName,content_type='text/plain')
        temp.close()
    except:
        pass


def mosaic_task(temp_folder_name:str, grayscale_flag: bool, focus_option:bool):
#--------------------------Set variables of program--------------------------------------------------------
    desired_height  = int(os.getenv('IMAGE_HIGHT', 20000))
    desired_width  = int(os.getenv('IMAGE_WIDTH', 18000))        
    grid_size = (36,18)
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(os.getenv('BUCKET_NAME'))
    
    if focus_option:
        blend_factor = 0.8
    else:
        blend_factor = 0.7

    update_state(temp_folder_name,state='PROGRESS', meta={'current': 10})

#------------------------------ Read target image and calcultae the shape--------------------------------------------------------
    target_img = 0
    for blob in bucket.list_blobs(prefix=temp_folder_name):
        if (blob.name).find("target_img") != -1:
            target_img = np.asarray(bytearray(blob.download_as_string()),dtype="uint8")
            target_img =cv2.imdecode(target_img,cv2.IMREAD_UNCHANGED)
            break
    
    if grayscale_flag:        
        target_img = cv2.cvtColor(target_img, cv2.COLOR_RGB2GRAY)
        target_h,target_w = target_img.shape[:2]
    else:
        target_h,target_w = target_img.shape[:2] 

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
    update_state(temp_folder_name,state='PROGRESS', meta={'current': 20})

#------------------------------ Read input images from zip file --------------------------------------------------------
    archive = 0
    for blob in bucket.list_blobs(prefix=temp_folder_name):
        if str(blob.name).find("temp_zip") != -1 :                
            zipbytes = io.BytesIO(blob.download_as_string())
            archive = ZipFile(zipbytes, 'r')
            break

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
    update_state(temp_folder_name,state='PROGRESS', meta={'current': 40})

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
                            
    archive.close()
    update_state(temp_folder_name,state='PROGRESS', meta={'current': 70})
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
        
      if(y >= target_h):
        loop_condition = False  
        break
    
    update_state(temp_folder_name,state='PROGRESS', meta={'current': 85})    
#------------------------------Save the final image--------------------------------------------------------
    archive = io.BytesIO()
    with ZipFile(archive, 'w', compression = ZIP_DEFLATED) as zip_archive:
        __, buf = cv2.imencode('.jpg', target_img)
        zip_archive.writestr("Image.jpg", buf)
    archive.seek(0)
    blob = bucket.blob(temp_folder_name + '/PhotoMosaic.zip')
    blob.upload_from_file(archive, content_type='application/zip')

#------------------------------Delete input_imgs_zip file and target_img--------------------------------------------------------
    try:
        for blob in bucket.list_blobs(prefix=temp_folder_name):
            blob_name = str(blob.name)
            if blob_name.find("PhotoMosaic") == -1 and blob_name.find("status") == -1 :
                blob.delete() 
    except :
        pass

    update_state(temp_folder_name,state='SUCCESS', meta={'current': 95})

#------------------------------Return temp folder name--------------------------------------------------------
    return temp_folder_name        
