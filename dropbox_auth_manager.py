# dropbox_auth_manager.py
import os
import requests
import json

class DropboxAuthManager:
    def __init__(self, app_key=None, app_secret=None):
        # Always store provided credentials
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = None
        
        # Try to load from file storage if no credentials provided
        if app_key is None or app_secret is None:
            self._try_load_from_file()
    
    def _get_credentials_file_path(self):
        """Get path to credentials file"""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(plugin_dir, ".dropbox_credentials.json")
    
    def _try_load_from_file(self):
        """Try to load credentials from JSON file"""
        try:
            credentials_path = self._get_credentials_file_path()
            if os.path.exists(credentials_path):
                with open(credentials_path, 'r') as f:
                    creds = json.load(f)
                
                if self.app_key is None:
                    self.app_key = creds.get("app_key")
                if self.app_secret is None:
                    self.app_secret = creds.get("app_secret")
                if self.refresh_token is None:
                    self.refresh_token = creds.get("refresh_token")
                
                print(f"[DropboxAuthManager] Loaded credentials from file: {credentials_path}")
                
        except Exception as e:
            print(f"[DropboxAuthManager] Could not load from credentials file: {e}")

    def is_connected(self):
        # Load from file if we don't have credentials yet
        if not (self.app_key and self.app_secret and self.refresh_token):
            self._try_load_from_file()
        return bool(self.app_key and self.app_secret and self.refresh_token)

    def store_tokens(self, app_key, app_secret, refresh_token):
        """Store tokens in JSON file"""
        try:
            credentials_path = self._get_credentials_file_path()
            
            credentials = {
                "app_key": app_key,
                "app_secret": app_secret,
                "refresh_token": refresh_token
            }
            
            print(f"[DropboxAuthManager] Storing tokens in file: {credentials_path}")
            with open(credentials_path, 'w') as f:
                json.dump(credentials, f, indent=2)
            
            # Set appropriate file permissions (readable only by owner)
            os.chmod(credentials_path, 0o600)
            
            # Update instance variables after successful storage
            self.app_key = app_key
            self.app_secret = app_secret
            self.refresh_token = refresh_token
            print(f"[DropboxAuthManager] Tokens stored successfully in credentials file")
            
        except Exception as e:
            error_msg = f"Failed to store Dropbox tokens: {e}"
            print(f"[DropboxAuthManager] {error_msg}")
            raise RuntimeError(error_msg)

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
        
        # If we get a 400 error and we're using a callback URL, try without it
        # This handles cases where the auth code was obtained without a callback URL
        if response.status_code == 400 and redirect_uri:
            print(f"[DropboxAuthManager] 400 error with callback URL, trying without callback URL...")
            
            data_without_redirect = {
                "code": auth_code,
                "grant_type": "authorization_code",
                "client_id": self.app_key,
                "client_secret": self.app_secret
            }
            
            print(f"[DropboxAuthManager] Retry request data (no callback URL): {data_without_redirect}")
            
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
        
        if revoke_token:
            # Load credentials from file first if we don't have them in memory
            if not (self.refresh_token and self.app_key and self.app_secret):
                print("[DropboxAuthManager] Loading credentials for token revocation...")
                self._try_load_from_file()
            
            # First, revoke the token with Dropbox if requested and possible
            if self.refresh_token and self.app_key and self.app_secret:
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
        else:
            print("[DropboxAuthManager] Skipping token revocation (revoke_token=False)")
        
        # Clear credentials file
        try:
            credentials_path = self._get_credentials_file_path()
            if os.path.exists(credentials_path):
                os.remove(credentials_path)
                print(f"[DropboxAuthManager] Removed credentials file: {credentials_path}")
        except Exception as e:
            print(f"[DropboxAuthManager] Could not remove credentials file: {e}")
        
        # Clear instance variables 
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

