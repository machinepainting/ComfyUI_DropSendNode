# ComfyUI_DropSendNode/setup_dropbox_node.py

import os
import requests
import webbrowser
import uuid
import json
from dotenv import load_dotenv, dotenv_values
import urllib.parse
from .dropbox_auth_manager import DropboxAuthManager
from .oauth_handler import OAuthCallbackHandler, get_server_base_url
from cryptography.fernet import Fernet

class DropboxSetupNode:
    @classmethod
    def INPUT_TYPES(cls):
        # Always show all fields for simplicity - no dynamic field hiding
        return {
            "required": {
                "app_key":             ("STRING", {"default": "", "multiline": False}),
                "app_secret":          ("STRING", {"default": "", "multiline": False}),
                "auth_code":           ("STRING", {"default": "", "multiline": False}),
                "dropbox_dest_folder": ("STRING", {"default": "/Apps/ComfyUI_Output_Files"}),
            },
            "optional": {
                "reconnect": ("BOOLEAN", {
                    "label": "Reset stored credentials",
                    "default": False
                }),
                "storage_method": (["env_file", "display_only"], {
                    "label": "Credential Storage Method",
                    "default": "display_only"
                }),
                "encryption_key_method": (["off", "Display Only", "save to .env"], {
                    "label": "Encryption Key Method",
                    "default": "Display Only"
                })
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "setup"

    def setup(self, dropbox_dest_folder, app_key=None, app_secret=None, auth_code=None, reconnect=False, storage_method="display_only", encryption_key_method="Display Only"):
        try:
            print(f"[DropboxSetup] Called with:")
            print(f"  app_key: '{app_key}' (type: {type(app_key)}, bool: {bool(app_key)})")
            print(f"  app_secret: '{app_secret}' (type: {type(app_secret)}, bool: {bool(app_secret)})")  
            print(f"  auth_code: '{auth_code}' (type: {type(auth_code)}, bool: {bool(auth_code)})")
            print(f"  reconnect: {reconnect}")
            print(f"  storage_method: {storage_method}")
            print(f"  encryption_key_method: {encryption_key_method}")
            
            # Initialize auth manager
            auth_manager = DropboxAuthManager()
            print(f"[DropboxSetup] Auth manager initialized")
            
            # Handle reconnect/reset request
            if reconnect:
                print("[DropboxSetup] Reconnect requested - clearing all credentials")
                
                # Clear all credentials (skip token revocation to avoid delays)
                print("[DropboxSetup] Clearing all stored credentials")
                auth_manager.reset(revoke_token=False)
                
                # Manually clear all credential files
                node_dir = os.path.dirname(__file__)
                
                # Clear .env file if it exists
                env_path = os.path.join(node_dir, ".env")
                if os.path.exists(env_path):
                    print(f"[DropboxSetup] Removing .env file: {env_path}")
                    os.remove(env_path)
                
                # Send WebSocket message to trigger ComfyUI refresh after clearing credentials
                try:
                    from server import PromptServer
                    message_data = {
                        "type": "dropbox_reconnect_complete",
                        "success": True,
                        "message": "Credentials cleared - ComfyUI will refresh to show auth fields"
                    }
                    PromptServer.instance.send_sync("dropbox_reconnect_complete", message_data)
                    print(f"[DropboxSetup] Sent WebSocket notification for reconnect completion")
                except Exception as e:
                    print(f"[DropboxSetup] Warning: Could not send WebSocket notification: {e}")
                
                message = "Dropbox credentials cleared. ComfyUI will refresh to show auth fields..."
                print(f"[DropboxSetup] {message}")
                return {
                    "ui": {"text": [message]},
                    "result": (message,)
                }
            
            # Check for environment variables (from any source)
            env_vars_set = all([
                os.getenv("DROPBOX_APP_KEY"),
                os.getenv("DROPBOX_APP_SECRET"), 
                os.getenv("DROPBOX_REFRESH_TOKEN")
            ])
            if env_vars_set:
                message = "Dropbox credentials found in system environment variables. Ready to upload files."
                print(f"[DropboxSetup] {message}")
                return {
                    "ui": {"text": [message]},
                    "result": (message,)
                }

            # Check for RunPod secrets
            runpod_env_set = all([
                os.getenv("RUNPOD_SECRET_DROPBOX_ACCESS_TOKEN"),
                os.getenv("RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
            ])
            if runpod_env_set:
                return ("Warning: Detected RunPod secrets. Using those instead.",)

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
                message = "Error: Missing App Key or App Secret. Please provide both."
                print(f"[DropboxSetup] {message}")
                return (message,)
            
            # If no auth code, generate OAuth URL for manual code flow
            if not auth_code_clean:
                print(f"[DropboxSetup] No auth code provided - generating OAuth URL for manual flow")
                auth_temp = DropboxAuthManager(app_key=app_key_clean)
                
                # Manual OAuth flow without redirect_uri (Dropbox will display the code)
                oauth_url = auth_temp.get_oauth_url(require_reapprove=True)
                
                try:
                    print(f"[DropboxSetup] Setting up manual OAuth popup...")
                    # JavaScript will automatically open a popup window
                    message = f"Dropbox OAuth Ready!\n\nClick the link below to authorize with Dropbox:\n\n{oauth_url}\n\nA popup window will open. After authorization, Dropbox will show your auth code.\nCopy the code and paste it into the 'auth_code' field above, then run this node again."
                    print(f"[DropboxSetup] OAuth URL ready for popup: {oauth_url}")
                except Exception as e:
                    print(f"[DropboxSetup] Error setting up OAuth: {e}")
                    message = f"Dropbox Authorization:\n\nPlease visit this URL to authorize:\n\n{oauth_url}\n\nAfter authorization, Dropbox will display your auth code. Copy it and paste into the 'auth_code' field above."
                
                print(f"[DropboxSetup] OAuth URL: {oauth_url}")
                
                # Use ComfyUI's dynamic return format for better UI integration
                return {
                    "ui": {"text": [message]},
                    "result": (message,)
                }

            # Exchange auth code for refresh token using DropboxAuthManager
            print(f"[DropboxSetup] Attempting to exchange auth code")
            auth_manager_setup = DropboxAuthManager(app_key_clean, app_secret_clean)
            
            # Get the tokens without storing them yet
            # Use manual OAuth flow (auth codes from manual copy/paste)
            print(f"[DropboxSetup] Using manual OAuth flow")
            result = auth_manager_setup.exchange_auth_code_raw(auth_code_clean)
            refresh_token = result.get("refresh_token")
            
            print(f"[DropboxSetup] Auth code exchange successful")
            print(f"[DropboxSetup] Using storage method: {storage_method}")
            
            # Generate encryption key only if encryption_key_method is not "off"
            encryption_key = None
            if encryption_key_method != "off":
                encryption_key = Fernet.generate_key().decode()
            
            # Prepare .env lines
            env_lines = []
            if storage_method == "env_file":
                env_lines.append(f"DROPBOX_APP_KEY={app_key_clean}")
                env_lines.append(f"DROPBOX_APP_SECRET={app_secret_clean}")
                env_lines.append(f"DROPBOX_REFRESH_TOKEN={refresh_token}")
                env_lines.append(f"DROPBOX_FOLDER={dropbox_dest_folder}")
            if encryption_key_method == "save to .env" and encryption_key:
                env_lines.append(f"COMFYUI_ENCRYPTION_KEY={encryption_key}")
            
            # Write to .env if there are lines to write
            if env_lines:
                node_dir = os.path.dirname(__file__)
                env_path = os.path.join(node_dir, ".env")
                with open(env_path, "w") as f:
                    f.write("\n".join(env_lines) + "\n")
            
            # Prepare display lines
            display_lines = []
            if storage_method == "display_only":
                display_lines.append(f"DROPBOX_APP_KEY={app_key_clean}")
                display_lines.append(f"DROPBOX_APP_SECRET={app_secret_clean}")
                display_lines.append(f"DROPBOX_REFRESH_TOKEN={refresh_token}")
                display_lines.append(f"DROPBOX_FOLDER={dropbox_dest_folder}")
            if encryption_key_method == "Display Only" and encryption_key:
                display_lines.append(f"COMFYUI_ENCRYPTION_KEY={encryption_key}")
            
            # Build message
            message = ""
            if storage_method == "env_file":
                message = "Dropbox connected successfully! Credentials saved to .env file."
            elif storage_method == "display_only":
                message = """Dropbox Connected Successfully!

=====================================================================
ENVIRONMENT VARIABLES - Copy & Paste Ready
=====================================================================

""" + "\n".join(display_lines) + """

=====================================================================
Perfect for RunPod, Docker, and production environments!
These credentials are ready to use immediately.
====================================================================="""
            
            # For display_only, ensure credentials are prominently shown in console
            if display_lines:
                print("\n" + "="*80)
                print("DROPBOX CREDENTIALS READY FOR PRODUCTION - COPY FROM CONSOLE")
                print("="*80)
                for line in display_lines:
                    print(line)
                print("="*80)
                print("Copy the lines above to your environment variables!")
                print("Perfect for RunPod, Docker, and production environments!")
                print("="*80 + "\n")
            
            print(f"[DropboxSetup] {message}")
            
            # Use ComfyUI's dynamic return format for better UI integration
            return {
                "ui": {"text": [message]},
                "result": (message,)
            }
            
        except Exception as e:
            message = f"Error: Setup failed: {e}"
            print(f"[DropboxSetup] ERROR: {message}")
            return {
                "ui": {"text": [message]},
                "result": (message,)
            }

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropboxSetupNode": DropboxSetupNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropboxSetupNode": "📦⚙️ DropSend - Setup Node"}