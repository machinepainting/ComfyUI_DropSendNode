# dropbox_upload.py
import os
import hashlib
import dropbox
import requests
from dropbox.exceptions import ApiError
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dropsend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_token():
    access_token = os.getenv("DROPBOX_ACCESS_TOKEN") or os.getenv("RUNPOD_SECRET_DROPBOX_ACCESS_TOKEN")
    if access_token:
        return access_token

    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN") or os.getenv("RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
    client_id = os.getenv("DROPBOX_APP_KEY") or os.getenv("RUNPOD_SECRET_DROPBOX_APP_KEY")
    client_secret = os.getenv("DROPBOX_APP_SECRET") or os.getenv("RUNPOD_SECRET_DROPBOX_APP_SECRET")

    missing = []
    if not refresh_token:
        missing.append("DROPBOX_REFRESH_TOKEN or RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
    if not client_id:
        missing.append("DROPBOX_APP_KEY or RUNPOD_SECRET_DROPBOX_APP_KEY")
    if not client_secret:
        missing.append("DROPBOX_APP_SECRET or RUNPOD_SECRET_DROPBOX_APP_SECRET")
    if missing:
        raise Exception(f"Missing Dropbox credentials: {', '.join(missing)}")

    try:
        response = requests.post(
            "https://api.dropbox.com/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to refresh Dropbox token: {str(e)}")

def upload_to_dropbox(local_file_path, dropbox_folder="/ComfyUI_Output_Files"):
    try:
        access_token = get_token()
        dbx = dropbox.Dropbox(access_token)

        try:
            dbx.files_get_metadata(dropbox_folder)
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                dbx.files_create_folder_v2(dropbox_folder)
                logger.info(f"📦📁 Created Dropbox folder: {dropbox_folder}")
            else:
                raise Exception(f"Failed to check/create Dropbox folder: {str(e)}")

        # Compute local file hash
        with open(local_file_path, "rb") as f:
            local_hash = hashlib.sha256(f.read()).hexdigest()

        # Upload file
        file_name = os.path.basename(local_file_path)
        dropbox_path = f"{dropbox_folder}/{file_name}"
        with open(local_file_path, "rb") as f:
            dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        # Verify upload integrity
        metadata, response = dbx.files_download(dropbox_path)
        remote_hash = hashlib.sha256(response.content).hexdigest()
        if local_hash != remote_hash:
            raise Exception(f"Upload integrity check failed for {dropbox_path}")

        logger.info(f"📦✅ Upload Verified: {dropbox_path}")
        return True  # Indicate successful upload and verification
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise Exception(f"Upload failed: {str(e)}")