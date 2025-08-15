# ComfyUI_DropSendNode/setup_dropbox_node.py

import os
import requests
from dotenv import load_dotenv, dotenv_values
import urllib.parse
from .dropbox_auth_manager import DropboxAuthManager


class DropboxSetupNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "app_key":             ("STRING", {"default": ""}),
                "app_secret":          ("STRING", {"default": ""}),
                "auth_code":           ("STRING", {"default": ""}),
                "dropbox_dest_folder": ("STRING", {"default": "/Apps/ComfyUI_Output_Files"}),
            },
            "optional": {
                "reconnect": ("BOOLEAN", {
                    "label": "Reconnect Dropbox (clear saved credentials)",
                    "default": False
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "setup"

    def setup(self, app_key, app_secret, auth_code, dropbox_dest_folder, reconnect=False):
        try:
            # Initialize auth manager
            auth_manager = DropboxAuthManager()
            
            # Handle reconnect/reset request
            if reconnect:
                auth_manager.reset()
                return ("🔄 Dropbox credentials cleared. Please provide new auth code to reconnect.",)
            
            # Check if already connected (keyring has credentials)
            if auth_manager.is_connected():
                # Test the stored credentials by getting an access token
                try:
                    access_token = auth_manager.get_access_token()
                    return ("✅ Dropbox already connected using stored credentials. Ready to upload files.",)
                except Exception as e:
                    return (f"⚠️ Stored credentials found but invalid: {e}. Use 'reconnect' to reset.",)
            
            # Check for legacy environment variables (keep existing fallback logic)
            general_env_set = all([
                os.getenv("DROPBOX_APP_KEY"),
                os.getenv("DROPBOX_APP_SECRET"),
                os.getenv("DROPBOX_REFRESH_TOKEN")
            ])
            if general_env_set:
                return ("⚠️ Dropbox credentials found in system environment variables. Using those instead of keyring.",)

            # Check for RunPod secrets
            runpod_env_set = all([
                os.getenv("RUNPOD_SECRET_DROPBOX_ACCESS_TOKEN"),
                os.getenv("RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
            ])
            if runpod_env_set:
                return ("⚠️ Detected RunPod secrets. Using those instead of keyring.",)

            # New setup flow using DropboxAuthManager
            if not all([app_key.strip(), app_secret.strip(), auth_code.strip()]):
                # Generate OAuth URL if no auth code provided
                if app_key.strip():
                    auth_temp = DropboxAuthManager(app_key=app_key.strip())
                    oauth_url = auth_temp.get_oauth_url()
                    return (f"❌ Missing credentials. Visit this URL to get auth code:\n{oauth_url}",)
                else:
                    return ("❌ Missing App Key, Secret, or Authorization Code.",)

            # Exchange auth code for refresh token using DropboxAuthManager
            auth_manager_setup = DropboxAuthManager(app_key.strip(), app_secret.strip())
            auth_manager_setup.exchange_auth_code(auth_code.strip())
            
            # Store destination folder in .env as fallback for other nodes
            node_dir = os.path.dirname(__file__)
            env_path = os.path.join(node_dir, ".env")
            with open(env_path, "w") as f:
                f.write(f"DROPBOX_FOLDER={dropbox_dest_folder}\n")
            
            return ("✅ Dropbox connected successfully! Credentials stored securely in system keyring.",)
            
        except Exception as e:
            return (f"❌ Setup failed: {e}",)

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropboxSetupNode": DropboxSetupNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropboxSetupNode": "📦⚙️ Dropbox AutoUploader Setup"}
