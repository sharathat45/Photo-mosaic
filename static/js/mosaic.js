function getMosaic()
{ 
    var target_Image = document.getElementById("FileUpload1").files;
    var input_Images = document.getElementById("filepicker").files;
    var image_option = document.getElementById('image_option').value;
    var focus_option = document.getElementById('focus_option').value;
    var formData = new FormData();
    
    if (image_option == "True"){image_option = true}
    else{image_option = false}
    if (focus_option == "True"){focus_option = true}
    else{focus_option = false}

    if (target_Image.length == 0)
    {
    Swal.fire({ title: "No target image selected",
                icon:'error',
                text: "choose one target image",
                allowOutsideClick: false}); 
    }
    else if(input_Images.length == 0)
    { 
    Swal.fire({ title: "No Background images selected",
                icon:'error',
                text: "Please select input images",
                allowOutsideClick: false});
    }
    else
    {   
        uploading_popup(true);
        formData.append("target_Image", target_Image[0]);
        
        var options = {
            method: 'POST',
            body: formData
        }

        fetch('/upload_files', options)
        .then(response => response.json())
        .then(data => upload_zip_file(data.SignedUrl, data.token))
        .catch(error =>{ 
            console.log('ERROR: ',error);
            uploading_popup(false); });
        
        function upload_zip_file(url,token)
        {
            zip_file = $('#filepicker')[0].files[0];
            
            url = url.replace(/\"/g, "")
            fetch(url, {
            method: 'PUT',
            body: zip_file
            })
            .then(response => response.text())
            .then(data => {
                console.log('done uploading...');
                start_task(token, image_option, focus_option); })
            .catch(error => {
                console.log('ERROR', error);
                uploading_popup(false); });
        } 
    }     
}

function start_task(Token, Image_option, Focus_option)
{
    var options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
          },
        body: JSON.stringify({
            token: Token,
            image_option: Image_option,
            focus_option: Focus_option
        })
    }

    fetch('/start_task',options)
    .then(response => response.json())
    .then(data => download_final_image(data.token))
    .catch(error => uploading_popup(false));
}

function download_final_image(token)
{
    Swal.fire({
        title: 'Computing mosaic',
        html:
            '<div class="progress">'+
                  '<div class="progress-done" data-done="8">'+
                        '8%'+
                  '</div>'+
            '</div>'+
            'Computing takes sometime, image will be automatically downloaded after computation', 
        showConfirmButton: false,
        allowEscapeKey: false,
        allowOutsideClick: false,
    })
    const progress = document.querySelector('.progress-done');
    progress.style.width = progress.getAttribute('data-done') + '%';
    progress.style.opacity = 1;
    
    var computation_flag = false;
    
    var checker = setInterval(function(){
    fetch('/api/status/'.concat(token))
    .then(response => response.json())
    .then(data => {
        if(data.state == "SUCCESS") { computation_flag = true; }
        else if(data.state == "PROGRESS" || data.state == "STARTED") { progress_fun(data.progress); }
        else {throw Error(response.statusText);}
    })
    .catch(error => retry(error)); 
    

    if(computation_flag == true)
    {
        location.href='https://storage.googleapis.com/photo-mosaic-00-urlsigner/'+ token + '/PhotoMosaic.zip'  
        
        stopChecker();
        Swal.close();
        Swal.fire({
        title: "Downloading!!",
        icon:'success',
        text: "Don't refresh!!, Image size is larger, It will download in a while...Check your downloads",
        timer:5000,
        didOpen: () => {Swal.showLoading();}
        }).then(result =>{
            document.getElementById("get_mosaic").style.visibility = "hidden";
            document.getElementById("FileUpload1").value = "";
            document.getElementById("filepicker").value = "";
        });     
        computation_flag = false;
    }
    }, 5000);

    function progress_fun(percentage)
    {
        if (percentage > 100) 
        {
            percentage = 100;
        }
        Swal.update({
            title: 'Computing mosaic',
            html:
                '<div class="progress">'+
                    '<div class="progress-done" data-done='+ percentage +'>'+
                            percentage+'%'+
                    '</div>'+
                '</div>'+
                'Image will be automatically downloaded after computation',
            showConfirmButton: false,
            allowEscapeKey: false,
            allowOutsideClick: false,
        })
        const progress = document.querySelector('.progress-done');
        progress.style.width = progress.getAttribute('data-done') + '%';
        progress.style.opacity = 1;
    }

    function retry(error)
    {
        stopChecker(); 
        Swal.close();
        Swal.fire(
        { 
            title: "Something went wrong!!",
            allowEscapeKey: false,
            allowOutsideClick: false,
            confirmButtonText: 'OK',
            icon:'error'
        }).then((result) => {
            if (result.isConfirmed){ location.reload(); } 
          });
                
    }

    function stopChecker() 
    { 
        clearInterval(checker);  
    }
}

function uploading_popup(state)
{
    if (state == true)
    {
        Swal.fire(
        {
            title: 'Uploading images',
            allowEscapeKey: false,
            allowOutsideClick: false,
            didOpen: () => {
            Swal.showLoading();
            }
        });
    }
    else if (state == false)
    {
        swal.close(); 
        Swal.fire(
        {
            title: 'Uploading failed',
            allowEscapeKey: false,
            allowOutsideClick: false,
            confirmButtonText: 'OK',
            icon:'error'
        }).then((result) => {
            if (result.isConfirmed){ location.reload(); } 
          });
        
    }
}        
