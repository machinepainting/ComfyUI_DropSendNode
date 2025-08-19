# dropbox_auth_manager.py
import os
import requests
import keyring
from keyring.errors import KeyringError

DROPBOX_KEYRING_SERVICE = "comfyui_dropbox"

def setup_keyring_backend():
    """Setup the best available keyring backend for the environment"""
    try:
        # Try to use the default backend first
        keyring.get_keyring()
        test_service = "test_keyring_availability"
        keyring.set_password(test_service, "test", "test")
        keyring.delete_password(test_service, "test")
        print("[DropboxAuthManager] Using system keyring backend")
        return True
    except Exception as e:
        print(f"[DropboxAuthManager] System keyring not available: {e}")
        
        # Try keyrings.alt file-based backends
        try:
            import keyrings.alt.file
            import keyrings.alt.cryptfile
            
            # Try encrypted file keyring first (more secure)
            try:
                crypto_keyring = keyrings.alt.cryptfile.CryptFileKeyring()
                # Set a simple password for the keyring file
                crypto_keyring.keyring_key = "comfyui_dropbox_keyring_2024"
                
                # Set custom file location in the plugin directory
                import os
                plugin_dir = os.path.dirname(os.path.abspath(__file__))
                crypto_keyring.filename = os.path.join(plugin_dir, ".dropbox_keyring.cfg")
                
                keyring.set_keyring(crypto_keyring)
                
                # Test it works
                test_service = "test_crypto_keyring"
                keyring.set_password(test_service, "test", "test")
                keyring.delete_password(test_service, "test")
                
                print(f"[DropboxAuthManager] Using encrypted file keyring: {crypto_keyring.filename}")
                return True
                
            except Exception as crypto_error:
                print(f"[DropboxAuthManager] Encrypted file keyring failed: {crypto_error}")
                
                # Fall back to plaintext file keyring
                try:
                    file_keyring = keyrings.alt.file.PlaintextKeyring()
                    
                    # Set custom file location in the plugin directory  
                    plugin_dir = os.path.dirname(os.path.abspath(__file__))
                    file_keyring.filename = os.path.join(plugin_dir, ".dropbox_keyring_plaintext.cfg")
                    
                    keyring.set_keyring(file_keyring)
                    
                    # Test it works
                    test_service = "test_file_keyring"
                    keyring.set_password(test_service, "test", "test")
                    keyring.delete_password(test_service, "test")
                    
                    print(f"[DropboxAuthManager] Using plaintext file keyring: {file_keyring.filename}")
                    print(f"[DropboxAuthManager] WARNING: Credentials will be stored in plaintext")
                    return True
                    
                except Exception as file_error:
                    print(f"[DropboxAuthManager] File keyring also failed: {file_error}")
                    return False
                    
        except ImportError as e:
            print(f"[DropboxAuthManager] keyrings.alt not available: {e}")
            print("[DropboxAuthManager] Install with: pip install keyrings.alt")
            return False
            
    except Exception as e:
        print(f"[DropboxAuthManager] All keyring backends failed: {e}")
        return False

class DropboxAuthManager:
    def __init__(self, app_key=None, app_secret=None):
        # Setup the best available keyring backend first
        self.keyring_available = setup_keyring_backend()
        
        # Try to get from keyring, but handle backend unavailability gracefully
        if self.keyring_available:
            try:
                self.app_key = app_key if app_key is not None else keyring.get_password(DROPBOX_KEYRING_SERVICE, "app_key")
                self.app_secret = app_secret if app_secret is not None else keyring.get_password(DROPBOX_KEYRING_SERVICE, "app_secret")
                self.refresh_token = keyring.get_password(DROPBOX_KEYRING_SERVICE, "refresh_token")
            except Exception as e:
                print(f"[DropboxAuthManager] Error reading from keyring: {e}")
                self.app_key = app_key
                self.app_secret = app_secret
                self.refresh_token = None
                self.keyring_available = False
        else:
            print(f"[DropboxAuthManager] No keyring backend available - using provided credentials only")
            self.app_key = app_key
            self.app_secret = app_secret
            self.refresh_token = None

    def is_connected(self):
        return bool(self.app_key and self.app_secret and self.refresh_token)

    def store_tokens(self, app_key, app_secret, refresh_token):
        if not self.keyring_available:
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

    def reset(self):
        """Clear stored tokens"""
        if self.keyring_available:
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

    def get_oauth_url(self, redirect_uri=None, state=None):
        """Generate OAuth URL for initial authorization"""
        if not self.app_key:
            raise ValueError("App key must be set to generate OAuth URL.")
        
        url = f"https://www.dropbox.com/oauth2/authorize?response_type=code&client_id={self.app_key}&token_access_type=offline"
        
        if redirect_uri:
            url += f"&redirect_uri={redirect_uri}"
        
        if state:
            url += f"&state={state}"
            
        return url

