# ComfyUI_DropSendNode/setup_dropbox_node.py

import os
import requests
from dotenv import load_dotenv, dotenv_values
from .runpod_utils import get_redirect_uri

class DropboxSetupNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "app_key":             ("STRING", {"default": ""}),
                "app_secret":          ("STRING", {"default": ""}),
                "auth_code":           ("STRING", {"default": ""}),
                "dropbox_dest_folder": ("STRING", {"default": "/Apps/ComfyUI_Output_Files"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "setup"

    def setup(self, app_key, app_secret, auth_code, dropbox_dest_folder):
        node_dir = os.path.dirname(__file__)
        env_path = os.path.join(node_dir, ".env")

        # 1. Skip setup if generic environment variables already exist
        general_env_set = all([
            os.getenv("DROPBOX_APP_KEY"),
            os.getenv("DROPBOX_APP_SECRET"),
            os.getenv("DROPBOX_REFRESH_TOKEN")
        ])
        if general_env_set:
            return ("⚠️ Dropbox credentials already set in system environment variables. Skipping .env creation.",)

        # 2. Skip setup if RunPod secrets are defined
        runpod_env_set = all([
            os.getenv("RUNPOD_SECRET_DROPBOX_ACCESS_TOKEN"),
            os.getenv("RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
        ])
        if runpod_env_set:
            return ("⚠️ Detected RunPod secrets (RUNPOD_SECRET_DROPBOX_ACCESS_TOKEN, RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN). Skipping .env creation.",)

        # 3. Run auth_code flow if no env config is present
        if not all([app_key, app_secret, auth_code]):
            return ("❌ Missing App Key, Secret, or Authorization Code.",)

        data = {
            "code": auth_code,
            "grant_type": "authorization_code",
            "client_id": app_key,
            "client_secret": app_secret,
            "redirect_uri": get_redirect_uri()
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        resp = requests.post("https://api.dropbox.com/oauth2/token", headers=headers, data=data)
        resp.raise_for_status()
        refresh_token = resp.json().get("refresh_token")

        # Write .env with fallback credentials
        with open(env_path, "w") as f:
            f.write(f"DROPBOX_APP_KEY={app_key}\n")
            f.write(f"DROPBOX_APP_SECRET={app_secret}\n")
            f.write(f"DROPBOX_REFRESH_TOKEN={refresh_token}\n")
            f.write(f"DROPBOX_FOLDER={dropbox_dest_folder}\n")

        load_dotenv(env_path, override=True)
        return ("✅ .env file created with Dropbox credentials.",)

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropboxSetupNode": DropboxSetupNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropboxSetupNode": "📦⚙️ Dropbox AutoUploader Setup"}
