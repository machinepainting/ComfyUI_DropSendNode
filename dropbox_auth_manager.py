# dropbox_auth_manager.py
import os
import requests
import keyring
from keyring.errors import KeyringError

DROPBOX_KEYRING_SERVICE = "comfyui_dropbox"

class DropboxAuthManager:
    def __init__(self, app_key=None, app_secret=None):
        self.app_key = app_key if app_key is not None else keyring.get_password(DROPBOX_KEYRING_SERVICE, "app_key")
        self.app_secret = app_secret if app_secret is not None else keyring.get_password(DROPBOX_KEYRING_SERVICE, "app_secret")
        self.refresh_token = keyring.get_password(DROPBOX_KEYRING_SERVICE, "refresh_token")

    def is_connected(self):
        return bool(self.app_key and self.app_secret and self.refresh_token)

    def store_tokens(self, app_key, app_secret, refresh_token):
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

    def exchange_auth_code(self, auth_code):
        if not (self.app_key and self.app_secret):
            raise ValueError("App key and secret must be set before exchanging auth code.")

        data = {
            "code": auth_code,
            "grant_type": "authorization_code",
            "client_id": self.app_key,
            "client_secret": self.app_secret
        }
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
        try:
            keyring.delete_password(DROPBOX_KEYRING_SERVICE, "app_key")
            keyring.delete_password(DROPBOX_KEYRING_SERVICE, "app_secret") 
            keyring.delete_password(DROPBOX_KEYRING_SERVICE, "refresh_token")
            
            # Clear instance variables
            self.app_key = None
            self.app_secret = None
            self.refresh_token = None
        except KeyringError:
            # If passwords don't exist, that's fine
            pass

    def get_oauth_url(self):
        """Generate OAuth URL for initial authorization"""
        if not self.app_key:
            raise ValueError("App key must be set to generate OAuth URL.")
        return f"https://www.dropbox.com/oauth2/authorize?response_type=code&client_id={self.app_key}&token_access_type=offline"

