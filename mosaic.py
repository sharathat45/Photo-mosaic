from PIL import Image, ImageOps 
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
    desired_height  = int(os.getenv('IMAGE_HIGHT', 10000))
    desired_width  = int(os.getenv('IMAGE_WIDTH', 7200))        
    grid_w = int(os.getenv('GRID_WIDTH', 700)) 
    grid_h = int(os.getenv('GRID_HIGHT', 400))  #std height images are (400X400) or (700X400) or (aspect_ratio_maintained_width X 400)
    ratio = (0.8,1.7)   #h/w ratio, if below lower threshold->landscape, above upper threshold->portrait, in between->square
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

    if(target_h/target_w  <= ratio[0]):  #if landscape image
        desired_height = desired_width
       
    hpercent = (desired_height/float(target_h))
    target_w = int((float(target_w)*float(hpercent)))
    target_h = desired_height        
    
    target_img = cv2.resize(target_img,(target_w, target_h), interpolation = cv2.INTER_CUBIC)
    update_state(temp_folder_name,state='PROGRESS', meta={'current': 15})

#------------------------------ Read input images from zip file --------------------------------------------------------
    archive = 0
    for blob in bucket.list_blobs(prefix=temp_folder_name):
        if str(blob.name).find("temp_zip") != -1 :                
            zipbytes = io.BytesIO(blob.download_as_string())
            archive = ZipFile(zipbytes, 'r')
            break

    files = archive.namelist()
    random.shuffle(files)

    images_list = []     #store extracted images
    images_list_iter = 0 #list iterator
    x=0                  # width
    y=0                  # height
    i = 0                #while loop iterator
    no_image_cnt = 0     #not images file count
    n = len(files)       #images to store/shift operation
    update_state(temp_folder_name,state='PROGRESS', meta={'current': 20})

#------------------------------ Resize input images , store and create final img--------------------------------------------------------
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
            update_state(temp_folder_name,state='PROGRESS', meta={'current': 20 + round(i/10)})   
        
        elif i==n: # shuffle images list after extraction from zip
            archive.close() 
            i+=1
            random.shuffle(images_list)
            n = n-no_image_cnt
            input_img = images_list[images_list_iter]
            h,w = input_img.shape[:2]
            images_list_iter +=1
            update_state(temp_folder_name,state='PROGRESS', meta={'current': 60})   
            
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
        
    update_state(temp_folder_name,state='PROGRESS', meta={'current': 80})    
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
