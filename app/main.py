import datetime
#import carb
import omni.client as client
#import omni.ext
import os
import jwt
import base64
import json
import requests
import signal
from fastapi import FastAPI, Request, Response, HTTPException, status, Security
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, ValueTarget
from starlette.requests import ClientDisconnect
#from omni.services.core import main
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import RSAAlgorithm
from fastapi import BackgroundTasks, FastAPI



#OvLink = os.getenv('OMNI_URL')
#OvUser = os.getenv('OMNI_USER')
#OvToken = os.getenv('OMNI_PASS')


OvLink = 'omniverse://192.168.1.17/Projects/'
OvUser = 'omniverse'
OvToken = '123456'

# Initialize your app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    #allow_methods=['POST', 'PUT', 'GET'],
    #allow_headers=['Authorization', 'Filename'],
    
    allow_methods=["*"],
    allow_headers=["*"],

    
)

security = HTTPBearer()
#K8S_MNT_PATH = '/mnt/nucleus/data/'
K8S_MNT_PATH = '/tmp'


# Initialize your app
#app = main.get_app()


file_location_dict = {
    'Collision Detection': 'collision_folder/',
    'File Conversion': 'file_storage/',
    'default': 'file_storage/'
}


class FileList(BaseModel):
    files: list


def log_handler(thread, component, level, message):
    print(f"{component}: {level}: {message}")


# Callback function to authorize to Nucleus Server
def default_authorize_callback(prefix):
    return OvUser, OvToken


def connect_server():
    client.register_authorize_callback(default_authorize_callback)
    client.set_log_level(client.LogLevel.WARNING)
    client.set_log_callback(log_handler)


def disconnect_server():
    client.sign_out(OvLink)

def printd(text):
    print(f'[{datetime.datetime.now()}] : {text} ', flush=True)

# Function to upload a file from Nucleus Server
def nucleus_upload(src_url: str, filename: str, overwrite: bool):
    printd(f'Start Uploading to Nucleus: ')

    try:
        printd(f'Start Uploading to Nucleus: src_url -> {src_url}')
        printd(f'                            dst     -> {OvLink+filename} {overwrite}')

        overwrite = True
        if overwrite:
            result = client.copy(src_url, OvLink + filename, client.CopyBehavior.OVERWRITE)
            printd(f'End Uploading to Nucleus:  ')
            return f'File Upload Successful by Overwriting. Status: {result}, File: {filename}'

        result = client.copy(src_url, OvLink + filename, client.CopyBehavior.ERROR_IF_EXISTS)

        if result == client.Result.ERROR_ALREADY_EXISTS:
            printd(f'File already exists. Status: {result}, File: {filename}')
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'The file {filename} already exists on the server.'
            )
        elif result == client.Result.OK:
            printd(f'End Uploading to Nucleus:')
            return f'File Upload Successful. Status: {result}, File: {filename}'
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'The file {filename} already exists on the server.'
            )

    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f'There was an error uploading the file {filename} to nucleus')




# Function to download a file from Nucleus Server
def download_file(file_name, job_type):
    if job_type not in file_location_dict:
        job_type = 'default'
    omni_path_split = (OvLink.rsplit('/', 1)[0]).rsplit('/', 1)[0] + '/'
    file_path = client.combine_urls(omni_path_split, file_location_dict[job_type] + file_name)
    return client.get_local_file(file_path, True)


# Function to remove files from temp memory
def remove_file(path):
    if os.path.isfile(path):
        os.remove(path)
        return True
    else:
        carb.log_error(f"Error: {path} file not found")
        return False


def validate_filename(request: Request) -> (str):
    printd(f'{request.headers}')
    filename = request.headers.get('Filename')
    if not filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Filename header is missing')

    if '.' not in filename or filename.rsplit('.', 1)[1] == '':
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail='Filename does not have a valid extension')

    return filename

async def handle_file_upload(request: Request, filepath: str):
    try:
        file_ = FileTarget(filepath)
        data = ValueTarget()
        printd(f"Well at least here - {filepath} {data}")
        parser = StreamingFormDataParser(headers=request.headers)
        printd("and probably not here")
        parser.register('file', file_)
        parser.register('data', data)

        async for chunk in request.stream():
            printd("B")
            parser.data_received(chunk)
            printd("#")

        printd("Monkey go home: mirice, look into this!!!!!")
        #if not file_.multipart_filename:
        #    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='File is missing')
        
        printd("final say")
    except ClientDisconnect:
        printd("Client Disconnected")
    except Exception as e:
        printd(f"Exception: {e.__class__.__name__}, Message: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='There was an error processing the file')

    printd("really?")

@app.get("/file")
async def download(fileName, jobType, background_tasks: BackgroundTasks):
    printd(f'fileName -> {fileName}')
    printd(f'jobType  ->  {jobType}')

    try:
        # download file locally using the path given in the fileName
        result, cached_local_path = download_file(fileName, jobType)
        # removes cached file from nucleus server after being sent
        background_tasks.add_task(remove_file, cached_local_path)
        return FileResponse(cached_local_path, media_type='application/octet-stream', filename=fileName)
    except:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail='There was an error downloading the file')


@app.post("/files")
async def upload_file(request: Request):

    printd(f'Start Uploading to PVC:  ')

    filename = validate_filename(request)

    filepath = os.path.join(K8S_MNT_PATH, os.path.basename(filename))

    printd(f'                      : {filepath}')

    await handle_file_upload(request, filepath)

    try:
        #carb.log_info(f'End Uploading to PVC:  ')
        nucleus_upload(filepath, filename, False)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail='There was an error uploading the file to Nucleus')
    finally:
        printd('mirice fix this, need the remove')
        #os.remove(filepath)

    return {'result': 'File Upload Successful'}


@app.get("/status")
def read_status():
    printd("got status request")
    return {"detail": "OK"}



#from fastapi import FastAPI
#import omni.client as client

#app = FastAPI()
#@app.get("/")
#def read_root():
#    return {"Hello": "World"}
#@app.get("/items/{item_id}")
#def read_item(item_id: int, q: str = None):
#    return {"item_id": item_id, "q": q}

