# ComfyUI_DropSendNode/setup_dropbox_node.py

import os
import requests
import webbrowser
import uuid
from dotenv import load_dotenv, dotenv_values
import urllib.parse
from .dropbox_auth_manager import DropboxAuthManager
from .oauth_handler import OAuthCallbackHandler


class DropboxSetupNode:
    @classmethod
    def INPUT_TYPES(cls):
        # Check if credentials are already stored (keyring or .env file)
        try:
            auth_manager = DropboxAuthManager()
            is_connected = auth_manager.is_connected()
            
            # If keyring is not available, we know keyring storage won't work
            if not auth_manager.keyring_available:
                print(f"[DropboxSetup] Keyring not available in this environment")
            
            # Also check for .env file credentials
            if not is_connected:
                node_dir = os.path.dirname(__file__)
                env_path = os.path.join(node_dir, ".env")
                if os.path.exists(env_path):
                    from dotenv import dotenv_values
                    env_vars = dotenv_values(env_path)
                    if all([env_vars.get("DROPBOX_APP_KEY"), env_vars.get("DROPBOX_APP_SECRET"), env_vars.get("DROPBOX_REFRESH_TOKEN")]):
                        is_connected = True
                        print(f"[DropboxSetup] Found credentials in .env file")
            
            # Also check for display_only completion marker - but only if environment variables actually exist
            if not is_connected:
                node_dir = os.path.dirname(__file__)
                display_marker_path = os.path.join(node_dir, ".dropbox_display_complete")
                if os.path.exists(display_marker_path):
                    # For display_only, verify that the user actually set up environment variables
                    display_only_env_set = all([
                        os.getenv("DROPBOX_APP_KEY"),
                        os.getenv("DROPBOX_APP_SECRET"),
                        os.getenv("DROPBOX_REFRESH_TOKEN")
                    ])
                    if display_only_env_set:
                        is_connected = True
                        print(f"[DropboxSetup] Found display_only completion marker with valid environment variables")
                    else:
                        print(f"[DropboxSetup] Found display_only completion marker but environment variables not set yet")
            
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
                "label": "🔄 Reconnect Dropbox (clears credentials & refreshes UI)",
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
            inputs["optional"]["auto_oauth"] = ("BOOLEAN", {
                "label": "Automatic OAuth (no manual auth code needed)",
                "default": True
            })
            # Smart default based on keyring availability
            if auth_manager.keyring_available:
                default_storage = "keyring"
                storage_options = ["keyring", "env_file", "display_only"]
            else:
                default_storage = "display_only"  # Better for RunPod/Docker
                storage_options = ["display_only", "env_file", "keyring"]
            
            inputs["optional"]["storage_method"] = (storage_options, {
                "label": "Credential Storage Method",
                "default": default_storage
            })
        
        return inputs

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "setup"

    def setup(self, dropbox_dest_folder, app_key=None, app_secret=None, auth_code=None, reconnect=False, auto_oauth=True, storage_method="keyring"):
        try:
            print(f"[DropboxSetup] Called with:")
            print(f"  app_key: '{app_key}' (type: {type(app_key)}, bool: {bool(app_key)})")
            print(f"  app_secret: '{app_secret}' (type: {type(app_secret)}, bool: {bool(app_secret)})")  
            print(f"  auth_code: '{auth_code}' (type: {type(auth_code)}, bool: {bool(auth_code)})")
            print(f"  reconnect: {reconnect}")
            print(f"  auto_oauth: {auto_oauth}")
            print(f"  storage_method: {storage_method}")
            
            # Initialize auth manager
            auth_manager = DropboxAuthManager()
            print(f"[DropboxSetup] Auth manager initialized. Is connected: {auth_manager.is_connected()}")
            
            # Handle reconnect/reset request
            if reconnect:
                print("[DropboxSetup] Reconnect requested - clearing credentials")
                
                # Clear keyring credentials
                auth_manager.reset()
                
                # Also clear .env file if it exists
                node_dir = os.path.dirname(__file__)
                env_path = os.path.join(node_dir, ".env")
                if os.path.exists(env_path):
                    print(f"[DropboxSetup] Removing .env file: {env_path}")
                    os.remove(env_path)
                
                # Also clear display_only marker if it exists
                display_marker_path = os.path.join(node_dir, ".dropbox_display_complete")
                if os.path.exists(display_marker_path):
                    print(f"[DropboxSetup] Removing display_only marker: {display_marker_path}")
                    os.remove(display_marker_path)
                
                # Send WebSocket message to trigger ComfyUI refresh after clearing credentials
                try:
                    from server import PromptServer
                    message_data = {
                        "type": "dropbox_reconnect_complete",
                        "success": True,
                        "message": "🔄 All credentials cleared - ComfyUI will refresh to show auth fields"
                    }
                    PromptServer.instance.send_sync("dropbox_reconnect_complete", message_data)
                    print(f"[DropboxSetup] Sent WebSocket notification for reconnect completion")
                except Exception as e:
                    print(f"[DropboxSetup] Warning: Could not send WebSocket notification: {e}")
                
                message = "🔄 Dropbox credentials cleared from all storage locations. ComfyUI will refresh to show auth fields..."
                print(f"[DropboxSetup] {message}")
                return {
                    "ui": {"text": [message]},
                    "result": (message,)
                }
            
            # Check if already connected (keyring has credentials)
            if auth_manager.is_connected():
                print("[DropboxSetup] Already connected - testing stored credentials")
                # Test the stored credentials by getting an access token
                try:
                    access_token = auth_manager.get_access_token()
                    message = "✅ Dropbox already connected using stored keyring credentials. Ready to upload files."
                    print(f"[DropboxSetup] {message}")
                    return {
                        "ui": {"text": [message]},
                        "result": (message,)
                    }
                except Exception as e:
                    message = f"⚠️ Stored credentials found but invalid: {e}. Use 'reconnect' to reset."
                    print(f"[DropboxSetup] {message}")
                    return {
                        "ui": {"text": [message]},
                        "result": (message,)
                    }
            
            # Check for display_only environment variables (user set them up after OAuth flow)
            display_only_env_set = all([
                os.getenv("DROPBOX_APP_KEY"),
                os.getenv("DROPBOX_APP_SECRET"), 
                os.getenv("DROPBOX_REFRESH_TOKEN")
            ])
            if display_only_env_set:
                # Check if this came from display_only flow
                node_dir = os.path.dirname(__file__)
                display_marker_path = os.path.join(node_dir, ".dropbox_display_complete")
                if os.path.exists(display_marker_path):
                    message = "✅ Dropbox connected using environment variables (display_only setup). Ready to upload files."
                    print(f"[DropboxSetup] {message}")
                    return {
                        "ui": {"text": [message]},
                        "result": (message,)
                    }
                else:
                    # Legacy environment variables (not from display_only)
                    message = "✅ Dropbox credentials found in system environment variables. Ready to upload files."
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
                
                if auto_oauth:
                    # Automatic OAuth flow with callback
                    session_id = str(uuid.uuid4())
                    callback_url = "http://localhost:8188/oauth/dropbox/callback"
                    oauth_url = auth_temp.get_oauth_url(redirect_uri=callback_url, state=session_id)
                    
                    # Set up OAuth session for callback handling
                    oauth_handler = OAuthCallbackHandler()
                    oauth_handler.start_oauth_session(session_id, app_key_clean, app_secret_clean, storage_method=storage_method, dropbox_folder=dropbox_dest_folder)
                    
                    try:
                        print(f"[DropboxSetup] Setting up automatic OAuth popup...")
                        # We'll use JavaScript to open a proper popup window
                        message = f"🚀 Automatic OAuth Ready!\n\n🖱️ Click the link below to open a small popup window for authorization:\n\n🔗 {oauth_url}\n\n✨ After authorization, the popup will close and ComfyUI will refresh automatically!"
                        print(f"[DropboxSetup] Session ID: {session_id}")
                        print(f"[DropboxSetup] Callback URL: {callback_url}")
                        print(f"[DropboxSetup] OAuth URL ready for popup: {oauth_url}")
                    except Exception as e:
                        print(f"[DropboxSetup] Error setting up OAuth: {e}")
                        message = f"🔗 Automatic OAuth Setup:\n\nPlease visit this URL to authorize:\n{oauth_url}\n\nAfter authorization, ComfyUI will refresh automatically!"
                else:
                    # Manual OAuth flow (original behavior)
                    oauth_url = auth_temp.get_oauth_url()
                    
                    try:
                        print(f"[DropboxSetup] Opening browser for manual OAuth flow...")
                        webbrowser.open(oauth_url)
                        message = f"🌐 Browser opened for Dropbox authorization!\n\n📋 After authorizing, paste the code in the auth_code field:\n{oauth_url}"
                    except Exception as e:
                        print(f"[DropboxSetup] Could not auto-open browser: {e}")
                        message = f"📋 Visit this URL to authorize, then paste the auth code:\n{oauth_url}"
                
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
            # Only pass redirect_uri if this was an automatic OAuth flow
            if auto_oauth:
                callback_url = "http://localhost:8188/oauth/dropbox/callback"
                print(f"[DropboxSetup] Using automatic OAuth with redirect_uri: {callback_url}")
                result = auth_manager_setup.exchange_auth_code_raw(auth_code_clean, redirect_uri=callback_url)
            else:
                print(f"[DropboxSetup] Using manual OAuth (no redirect_uri)")
                result = auth_manager_setup.exchange_auth_code_raw(auth_code_clean)
            refresh_token = result.get("refresh_token")
            
            print(f"[DropboxSetup] Auth code exchange successful")
            print(f"[DropboxSetup] Using storage method: {storage_method}")
            
            # Handle different storage methods
            if storage_method == "keyring":
                # Store in system keyring (original behavior)
                try:
                    auth_manager_setup.store_tokens(app_key_clean, app_secret_clean, refresh_token)
                    message = "✅ Dropbox connected successfully! Credentials stored securely in system keyring."
                except RuntimeError as e:
                    if "Keyring not available" in str(e):
                        message = f"❌ All keyring backends failed in this environment.\n\n💡 Please use 'env_file' or 'display_only' storage method instead.\n\n🔧 To enable file-based keyring, ensure 'keyrings.alt' is installed.\n\nTechnical details: {e}"
                    else:
                        raise e
                
            elif storage_method == "env_file":
                # Store in .env file
                node_dir = os.path.dirname(__file__)
                env_path = os.path.join(node_dir, ".env")
                with open(env_path, "w") as f:
                    f.write(f"DROPBOX_APP_KEY={app_key_clean}\n")
                    f.write(f"DROPBOX_APP_SECRET={app_secret_clean}\n")
                    f.write(f"DROPBOX_REFRESH_TOKEN={refresh_token}\n")
                    f.write(f"DROPBOX_FOLDER={dropbox_dest_folder}\n")
                message = "✅ Dropbox connected successfully! Credentials saved to .env file."
                
            elif storage_method == "display_only":
                # Display credentials for manual copying and create completion marker
                node_dir = os.path.dirname(__file__)
                display_marker_path = os.path.join(node_dir, ".dropbox_display_complete")
                with open(display_marker_path, "w") as f:
                    f.write("display_only_setup_completed")
                
                message = f"""✅ Dropbox Connected Successfully!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 ENVIRONMENT VARIABLES - Copy & Paste Ready
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DROPBOX_APP_KEY={app_key_clean}

DROPBOX_APP_SECRET={app_secret_clean}

DROPBOX_REFRESH_TOKEN={refresh_token}

DROPBOX_FOLDER={dropbox_dest_folder}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Perfect for RunPod, Docker, and production environments!
🚀 These credentials are ready to use immediately.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
                
            else:
                # Fallback to keyring
                auth_manager_setup.store_tokens(app_key_clean, app_secret_clean, refresh_token)
                message = "✅ Dropbox connected successfully! Credentials stored securely in system keyring."
            
            print(f"[DropboxSetup] {message}")
            
            # For display_only, ensure credentials are prominently shown in console
            if storage_method == "display_only":
                print("\n" + "="*60)
                print("🔥 DROPBOX CREDENTIALS READY FOR PRODUCTION 🔥")
                print("="*60)
                print(f"DROPBOX_APP_KEY={app_key_clean}")
                print(f"DROPBOX_APP_SECRET={app_secret_clean}")
                print(f"DROPBOX_REFRESH_TOKEN={refresh_token}")
                print(f"DROPBOX_FOLDER={dropbox_dest_folder}")
                print("="*60)
                print("📋 Copy these to your environment variables!")
                print("="*60 + "\n")
            
            # Use ComfyUI's dynamic return format for better UI integration
            return {
                "ui": {"text": [message]},
                "result": (message,)
            }
            
        except Exception as e:
            message = f"❌ Setup failed: {e}"
            print(f"[DropboxSetup] ERROR: {message}")
            return {
                "ui": {"text": [message]},
                "result": (message,)
            }

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropboxSetupNode": DropboxSetupNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropboxSetupNode": "📦⚙️ Dropbox AutoUploader Setup"}
