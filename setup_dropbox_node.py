# ComfyUI_DropSendNode/setup_dropbox_node.py

import os
import requests
from dotenv import load_dotenv, dotenv_values
import urllib.parse
from .dropbox_auth_manager import DropboxAuthManager


class DropboxSetupNode:
    @classmethod
    def INPUT_TYPES(cls):
        # Check if credentials are already stored
        try:
            auth_manager = DropboxAuthManager()
            is_connected = auth_manager.is_connected()
            print(f"[DropboxSetup] INPUT_TYPES check - is_connected: {is_connected}")
        except Exception as e:
            print(f"[DropboxSetup] INPUT_TYPES error: {e}")
            is_connected = False
        
        # Base inputs that are always shown
        inputs = {
            "required": {
                "dropbox_dest_folder": ("STRING", {"default": "/Apps/ComfyUI_Output_Files"}),
            },
            "optional": {}
        }
        
        if is_connected:
            # If connected, only show reconnect option
            inputs["optional"]["reconnect"] = ("BOOLEAN", {
                "label": "Reconnect Dropbox (clear saved credentials)",
                "default": False
            })
        else:
            # If not connected, show setup fields
            inputs["required"].update({
                "app_key":    ("STRING", {"default": "", "multiline": False}),
                "app_secret": ("STRING", {"default": "", "multiline": False}),
                "auth_code":  ("STRING", {"default": "", "multiline": False}),
            })
            inputs["optional"]["reconnect"] = ("BOOLEAN", {
                "label": "Reset stored credentials",
                "default": False
            })
        
        return inputs

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "setup"

    def setup(self, dropbox_dest_folder, app_key=None, app_secret=None, auth_code=None, reconnect=False):
        try:
            print(f"[DropboxSetup] Called with:")
            print(f"  app_key: '{app_key}' (type: {type(app_key)}, bool: {bool(app_key)})")
            print(f"  app_secret: '{app_secret}' (type: {type(app_secret)}, bool: {bool(app_secret)})")  
            print(f"  auth_code: '{auth_code}' (type: {type(auth_code)}, bool: {bool(auth_code)})")
            print(f"  reconnect: {reconnect}")
            
            # Initialize auth manager
            auth_manager = DropboxAuthManager()
            print(f"[DropboxSetup] Auth manager initialized. Is connected: {auth_manager.is_connected()}")
            
            # Handle reconnect/reset request
            if reconnect:
                print("[DropboxSetup] Reconnect requested - clearing credentials")
                auth_manager.reset()
                message = "🔄 Dropbox credentials cleared. Please provide new auth code to reconnect."
                print(f"[DropboxSetup] {message}")
                return (message,)
            
            # Check if already connected (keyring has credentials)
            if auth_manager.is_connected():
                print("[DropboxSetup] Already connected - testing stored credentials")
                # Test the stored credentials by getting an access token
                try:
                    access_token = auth_manager.get_access_token()
                    message = "✅ Dropbox already connected using stored credentials. Ready to upload files."
                    print(f"[DropboxSetup] {message}")
                    return (message,)
                except Exception as e:
                    message = f"⚠️ Stored credentials found but invalid: {e}. Use 'reconnect' to reset."
                    print(f"[DropboxSetup] {message}")
                    return (message,)
            
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
            print(f"[DropboxSetup] Starting new setup flow")
            
            # Clean up the inputs first
            app_key_clean = app_key.strip() if app_key else ""
            app_secret_clean = app_secret.strip() if app_secret else ""
            auth_code_clean = auth_code.strip() if auth_code else ""
            
            print(f"[DropboxSetup] Cleaned inputs:")
            print(f"  app_key_clean: '{app_key_clean}' (len: {len(app_key_clean)})")
            print(f"  app_secret_clean: '{app_secret_clean}' (len: {len(app_secret_clean)})")
            print(f"  auth_code_clean: '{auth_code_clean}' (len: {len(auth_code_clean)})")
            
            # Check if we have app credentials
            if not app_key_clean or not app_secret_clean:
                message = "❌ Missing App Key or App Secret. Please provide both."
                print(f"[DropboxSetup] {message}")
                return (message,)
            
            # If no auth code, generate OAuth URL
            if not auth_code_clean:
                print(f"[DropboxSetup] No auth code provided - generating OAuth URL")
                auth_temp = DropboxAuthManager(app_key=app_key_clean)
                oauth_url = auth_temp.get_oauth_url()
                message = f"📋 Visit this URL to authorize, then paste the auth code:\n{oauth_url}"
                print(f"[DropboxSetup] OAuth URL: {oauth_url}")
                return (message,)

            # Exchange auth code for refresh token using DropboxAuthManager
            print(f"[DropboxSetup] Attempting to exchange auth code")
            auth_manager_setup = DropboxAuthManager(app_key_clean, app_secret_clean)
            auth_manager_setup.exchange_auth_code(auth_code_clean)
            print(f"[DropboxSetup] Auth code exchange successful")
            
            # Store destination folder in .env as fallback for other nodes
            node_dir = os.path.dirname(__file__)
            env_path = os.path.join(node_dir, ".env")
            with open(env_path, "w") as f:
                f.write(f"DROPBOX_FOLDER={dropbox_dest_folder}\n")
            print(f"[DropboxSetup] Stored destination folder: {dropbox_dest_folder}")
            
            message = "✅ Dropbox connected successfully! Credentials stored securely in system keyring."
            print(f"[DropboxSetup] {message}")
            return (message,)
            
        except Exception as e:
            message = f"❌ Setup failed: {e}"
            print(f"[DropboxSetup] ERROR: {message}")
            return (message,)

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropboxSetupNode": DropboxSetupNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropboxSetupNode": "📦⚙️ Dropbox AutoUploader Setup"}
