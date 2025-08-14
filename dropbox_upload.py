import os
import dropbox
import requests
from dropbox.exceptions import ApiError

def get_token():
    # 1. Prioritize direct access_token from environment variables
    access_token = os.getenv("DROPBOX_ACCESS_TOKEN") or os.getenv("RUNPOD_SECRET_DROPBOX_ACCESS_TOKEN")
    if access_token:
        return access_token

    # 2. Try refresh_token flow from environment variables or RunPod secrets
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN") or os.getenv("RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
    client_id = os.getenv("DROPBOX_APP_KEY") or os.getenv("RUNPOD_SECRET_DROPBOX_APP_KEY")
    client_secret = os.getenv("DROPBOX_APP_SECRET") or os.getenv("RUNPOD_SECRET_DROPBOX_APP_SECRET")

    # 3. Check if all required credentials are present
    missing = []
    if not refresh_token:
        missing.append("DROPBOX_REFRESH_TOKEN or RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
    if not client_id:
        missing.append("DROPBOX_APP_KEY or RUNPOD_SECRET_DROPBOX_APP_KEY")
    if not client_secret:
        missing.append("DROPBOX_APP_SECRET or RUNPOD_SECRET_DROPBOX_APP_SECRET")
    if missing:
        raise Exception(f"❌ Missing Dropbox credentials: {', '.join(missing)}")

    # 4. Perform OAuth refresh token flow
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
        raise Exception(f"❌ Failed to refresh Dropbox token: {str(e)}")

def upload_to_dropbox(local_file_path, dropbox_folder="/ComfyUI_Output_Files"):
    try:
        # Initialize Dropbox client
        access_token = get_token()
        dbx = dropbox.Dropbox(access_token)

        # Ensure the Dropbox folder exists
        try:
            dbx.files_get_metadata(dropbox_folder)
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                dbx.files_create_folder_v2(dropbox_folder)
                print(f"📁 Created Dropbox folder: {dropbox_folder}")
            else:
                raise Exception(f"❌ Failed to check/create Dropbox folder: {str(e)}")

        # Upload the file
        file_name = os.path.basename(local_file_path)
        dropbox_path = f"{dropbox_folder}/{file_name}"
        with open(local_file_path, "rb") as f:
            dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)
        print(f"📦📤 Uploaded to Dropbox: {dropbox_path}")
    except Exception as e:
        raise Exception(f"❌ Upload failed: {str(e)}")
