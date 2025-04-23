# ComfyUI_DropSendNode/dropbox_upload.py

import os
import dropbox
import requests
from dotenv import load_dotenv

def get_token():
    # 1. Prioritize direct access_token from general environment variables
    access_token = os.getenv("DROPBOX_ACCESS_TOKEN")
    if access_token:
        return access_token

    # 2. Try refresh_token flow from general environment variables
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
    client_id     = os.getenv("DROPBOX_APP_KEY")
    client_secret = os.getenv("DROPBOX_APP_SECRET")

    # 3. If missing, check for RunPod-style prefixed secrets
    refresh_token = refresh_token or os.getenv("RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
    access_token  = os.getenv("RUNPOD_SECRET_DROPBOX_ACCESS_TOKEN")
    if access_token:
        return access_token

    # 4. Final fallback: load from .env for local users
    if not all([refresh_token, client_id, client_secret]):
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
            refresh_token = refresh_token or os.getenv("DROPBOX_REFRESH_TOKEN") or os.getenv("RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
            client_id     = client_id or os.getenv("DROPBOX_APP_KEY")
            client_secret = client_secret or os.getenv("DROPBOX_APP_SECRET")

    if not all([refresh_token, client_id, client_secret]):
        raise Exception("❌ Missing Dropbox credentials. Define them as environment variables or in a .env file.")

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

def upload_to_dropbox(local_file_path, dropbox_folder="/Apps/ComfyUI_Output_Files"):
    access_token = get_token()
    dbx = dropbox.Dropbox(access_token)

    file_name = os.path.basename(local_file_path)
    dropbox_path = f"{dropbox_folder}/{file_name}"

    with open(local_file_path, "rb") as f:
        dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

    print(f"📦📤 Uploaded to Dropbox: {dropbox_path}")
