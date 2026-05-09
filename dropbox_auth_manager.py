# dropbox_auth_manager.py
import os
import logging
import requests
import json

logger = logging.getLogger(__name__)

class DropboxAuthManager:
    def __init__(self, app_key=None, app_secret=None, refresh_token=None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token

    def _get_credentials_file_path(self):
        """Path to a legacy JSON credential file from older versions.

        The current code never writes this file — credentials live in
        `.env` (or are delivered to the browser via WebSocket and never
        touch disk). The path is kept only so reset() can clean up a
        stale file left over from earlier installs.
        """
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(plugin_dir, ".dropbox_credentials.json")

    def is_connected(self):
        return bool(self.app_key and self.app_secret and self.refresh_token)

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

        # Do not log `data` or `response.text` here — both contain secrets
        # (client_secret, refresh_token, access_token). On platforms that
        # capture stdout (RunPod, Docker, CI) those would land in shared logs.
        response = requests.post("https://api.dropbox.com/oauth2/token", headers=headers, data=data)

        print(f"[DropboxAuthManager] Token exchange response status: {response.status_code}")

        # If 400 error, try without redirect_uri. This handles cases where
        # the auth code was obtained without a callback URL.
        if response.status_code == 400 and redirect_uri:
            print("[DropboxAuthManager] 400 with redirect_uri, retrying without it")

            data_without_redirect = {
                "code": auth_code,
                "grant_type": "authorization_code",
                "client_id": self.app_key,
                "client_secret": self.app_secret
            }

            response = requests.post("https://api.dropbox.com/oauth2/token", headers=headers, data=data_without_redirect)
            print(f"[DropboxAuthManager] Retry response status: {response.status_code}")

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
            # Revoke the token with Dropbox if we have it in memory.
            # The legacy auto-load from .dropbox_credentials.json is gone;
            # callers that want to revoke must construct this manager with
            # creds (or set them) before calling reset(revoke_token=True).
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
                        json=revoke_data,
                        # Bound the wait so a Dropbox outage or DNS
                        # failure doesn't hang the user mid-reconnect.
                        # Local-cleanup is the priority here; the
                        # token-revoke is best-effort (and Dropbox
                        # tokens expire on their own anyway).
                        timeout=8,
                    )
                    
                    if response.status_code == 200:
                        msg = "[DropboxAuthManager] Token successfully revoked with Dropbox"
                        print(msg)
                        logger.info(msg)
                    else:
                        # Don't log response.text — it can echo the access token on some failures.
                        msg = (
                            f"[DropboxAuthManager] Token revocation FAILED at Dropbox "
                            f"(HTTP {response.status_code}). The refresh token may still "
                            f"be valid. Manually disconnect at "
                            f"https://www.dropbox.com/account/connected_apps to be sure."
                        )
                        print(msg)
                        logger.error(msg)
                except Exception as e:
                    # Common case: Dropbox unreachable, refresh token already
                    # invalidated, or get_access_token() couldn't mint one.
                    # Local cleanup proceeds, but the operator needs to know
                    # the token may still be live at Dropbox.
                    msg = (
                        f"[DropboxAuthManager] Token revocation FAILED locally: {e}. "
                        f"The refresh token may still be valid at Dropbox. Manually "
                        f"disconnect at https://www.dropbox.com/account/connected_apps."
                    )
                    print(msg)
                    logger.error(msg)
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

