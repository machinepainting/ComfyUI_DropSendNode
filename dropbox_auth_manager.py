# dropbox_auth_manager.py
import os
import requests
import keyring
from keyring.errors import KeyringError

DROPBOX_KEYRING_SERVICE = "comfyui_dropbox"

def setup_keyring_backend():
    """Setup the best available keyring backend for the environment - non-blocking"""
    try:
        # Try to use the default backend first (non-interactive)
        current_keyring = keyring.get_keyring()
        keyring_name = current_keyring.__class__.__name__
        
        # Skip interactive/password-prompting keyrings during startup
        if 'crypt' in keyring_name.lower() or 'gnome' in keyring_name.lower():
            print(f"[DropboxAuthManager] Skipping interactive keyring ({keyring_name}) to avoid blocking startup")
            raise Exception("Interactive keyring detected - using fallback")
        
        # Test non-interactively
        test_service = "test_keyring_availability"
        keyring.set_password(test_service, "test", "test")
        keyring.delete_password(test_service, "test")
        print(f"[DropboxAuthManager] Using system keyring backend: {keyring_name}")
        return True
        
    except Exception as e:
        print(f"[DropboxAuthManager] System keyring not available or interactive: {e}")
        
        # Try keyrings.alt file-based backends
        try:
            import keyrings.alt.file
            
            # Use plaintext file keyring (non-interactive, works reliably)
            file_keyring = keyrings.alt.file.PlaintextKeyring()
            
            # Set custom file location in the plugin directory  
            import os
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            file_keyring.filename = os.path.join(plugin_dir, ".dropbox_keyring_plaintext.cfg")
            
            keyring.set_keyring(file_keyring)
            
            # Test it works
            test_service = "test_file_keyring"
            keyring.set_password(test_service, "test", "test")
            keyring.delete_password(test_service, "test")
            
            print(f"[DropboxAuthManager] Using plaintext file keyring: {file_keyring.filename}")
            print(f"[DropboxAuthManager] NOTE: Credentials stored in plugin directory (not system keyring)")
            return True
                    
        except ImportError as e:
            print(f"[DropboxAuthManager] keyrings.alt not available: {e}")
            print("[DropboxAuthManager] Install with: pip install keyrings.alt")
            return False
        except Exception as file_error:
            print(f"[DropboxAuthManager] File keyring failed: {file_error}")
            return False
            
    except Exception as e:
        print(f"[DropboxAuthManager] All keyring backends failed: {e}")
        return False

class DropboxAuthManager:
    def __init__(self, app_key=None, app_secret=None):
        # Don't set up keyring during initialization - do it lazily when needed
        self.keyring_available = None  # Unknown until first access
        self.keyring_tested = False
        
        # Always store provided credentials
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = None
        
        # Try to load from keyring only if no credentials provided
        if app_key is None or app_secret is None:
            self._try_load_from_keyring()
    
    def _ensure_keyring_setup(self):
        """Set up keyring backend only when needed (lazy initialization)"""
        if not self.keyring_tested:
            self.keyring_available = setup_keyring_backend()
            self.keyring_tested = True
        return self.keyring_available
    
    def _try_load_from_keyring(self):
        """Try to load credentials from keyring, but don't block if unavailable"""
        try:
            if self._ensure_keyring_setup():
                if self.app_key is None:
                    self.app_key = keyring.get_password(DROPBOX_KEYRING_SERVICE, "app_key")
                if self.app_secret is None:
                    self.app_secret = keyring.get_password(DROPBOX_KEYRING_SERVICE, "app_secret")
                if self.refresh_token is None:
                    self.refresh_token = keyring.get_password(DROPBOX_KEYRING_SERVICE, "refresh_token")
        except Exception as e:
            print(f"[DropboxAuthManager] Could not load from keyring: {e}")
            # Don't fail - just continue without keyring credentials

    def is_connected(self):
        return bool(self.app_key and self.app_secret and self.refresh_token)

    def store_tokens(self, app_key, app_secret, refresh_token):
        if not self._ensure_keyring_setup():
            raise RuntimeError("Keyring not available. Please use 'env_file' or 'display_only' storage method instead.")
        
        try:
            keyring.set_password(DROPBOX_KEYRING_SERVICE, "app_key", app_key)
            keyring.set_password(DROPBOX_KEYRING_SERVICE, "app_secret", app_secret)
            keyring.set_password(DROPBOX_KEYRING_SERVICE, "refresh_token", refresh_token)
            
            # Update instance variables after successful storage
            self.app_key = app_key
            self.app_secret = app_secret
            self.refresh_token = refresh_token
        except KeyringError as e:
            raise RuntimeError(f"Failed to store Dropbox tokens securely: {e}")

    def exchange_auth_code(self, auth_code, redirect_uri=None):
        if not (self.app_key and self.app_secret):
            raise ValueError("App key and secret must be set before exchanging auth code.")

        data = {
            "code": auth_code,
            "grant_type": "authorization_code",
            "client_id": self.app_key,
            "client_secret": self.app_secret
        }
        
        # Include redirect_uri if it was used in the authorization request
        if redirect_uri:
            data["redirect_uri"] = redirect_uri
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post("https://api.dropbox.com/oauth2/token", headers=headers, data=data)
        response.raise_for_status()

        creds = response.json()
        refresh_token = creds.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("Failed to obtain refresh token from Dropbox.")

        self.store_tokens(self.app_key, self.app_secret, refresh_token)
        self.refresh_token = refresh_token
        return True
    
    def exchange_auth_code_raw(self, auth_code, redirect_uri=None):
        """Exchange auth code for tokens without storing them"""
        if not (self.app_key and self.app_secret):
            raise ValueError("App key and secret must be set before exchanging auth code.")

        data = {
            "code": auth_code,
            "grant_type": "authorization_code",
            "client_id": self.app_key,
            "client_secret": self.app_secret
        }
        
        # Include redirect_uri if it was used in the authorization request
        if redirect_uri:
            data["redirect_uri"] = redirect_uri
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        print(f"[DropboxAuthManager] Token exchange request data: {data}")
        print(f"[DropboxAuthManager] Making request to: https://api.dropbox.com/oauth2/token")
        
        response = requests.post("https://api.dropbox.com/oauth2/token", headers=headers, data=data)
        
        print(f"[DropboxAuthManager] Response status: {response.status_code}")
        print(f"[DropboxAuthManager] Response text: {response.text}")
        
        # If we get a 400 error and we're using a redirect_uri, try without it
        # This handles cases where the auth code was obtained without the redirect_uri
        if response.status_code == 400 and redirect_uri:
            print(f"[DropboxAuthManager] 400 error with redirect_uri, trying without redirect_uri...")
            
            data_without_redirect = {
                "code": auth_code,
                "grant_type": "authorization_code",
                "client_id": self.app_key,
                "client_secret": self.app_secret
            }
            
            print(f"[DropboxAuthManager] Retry request data (no redirect_uri): {data_without_redirect}")
            
            response = requests.post("https://api.dropbox.com/oauth2/token", headers=headers, data=data_without_redirect)
            
            print(f"[DropboxAuthManager] Retry response status: {response.status_code}")
            print(f"[DropboxAuthManager] Retry response text: {response.text}")
        
        response.raise_for_status()

        return response.json()

    def get_access_token(self):
        if not self.is_connected():
            raise RuntimeError("Dropbox not connected. Please run authentication first.")

        data = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "client_id": self.app_key,
            "client_secret": self.app_secret
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post("https://api.dropbox.com/oauth2/token", headers=headers, data=data)
        response.raise_for_status()

        access_token = response.json().get("access_token")
        if not access_token:
            raise RuntimeError("Failed to retrieve access token.")
        return access_token

    def reset(self, revoke_token=True):
        """Clear stored tokens and optionally revoke authorization with Dropbox"""
        
        # First, revoke the token with Dropbox if requested and possible
        if revoke_token and self.refresh_token and self.app_key and self.app_secret:
            try:
                print("[DropboxAuthManager] Revoking token with Dropbox...")
                
                # Get current access token to revoke
                access_token = self.get_access_token()
                
                # Revoke the token with Dropbox
                revoke_data = {
                    "token": access_token
                }
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(
                    "https://api.dropboxapi.com/2/auth/token/revoke",
                    headers=headers,
                    json=revoke_data
                )
                
                if response.status_code == 200:
                    print("[DropboxAuthManager] Token successfully revoked with Dropbox")
                else:
                    print(f"[DropboxAuthManager] Token revocation failed: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"[DropboxAuthManager] Could not revoke token with Dropbox: {e}")
                # Continue with local cleanup even if revocation fails
        
        # Clear from keyring
        if self._ensure_keyring_setup():
            try:
                keyring.delete_password(DROPBOX_KEYRING_SERVICE, "app_key")
                keyring.delete_password(DROPBOX_KEYRING_SERVICE, "app_secret") 
                keyring.delete_password(DROPBOX_KEYRING_SERVICE, "refresh_token")
            except KeyringError:
                # If passwords don't exist, that's fine
                pass
        
        # Clear instance variables regardless of keyring availability
        self.app_key = None
        self.app_secret = None
        self.refresh_token = None

    def get_oauth_url(self, redirect_uri=None, state=None, force_reapprove=False):
        """Generate OAuth URL for initial authorization"""
        if not self.app_key:
            raise ValueError("App key must be set to generate OAuth URL.")
        
        url = f"https://www.dropbox.com/oauth2/authorize?response_type=code&client_id={self.app_key}&token_access_type=offline"
        
        if redirect_uri:
            url += f"&redirect_uri={redirect_uri}"
        
        if state:
            url += f"&state={state}"
        
        # Force reapproval to ensure user sees authorization screen
        if force_reapprove:
            url += "&force_reapprove=true"
            
        return url

