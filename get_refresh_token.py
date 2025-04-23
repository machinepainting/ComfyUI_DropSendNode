# ComfyUI_DropSendNode/get_refresh_token.py

import base64
import requests

APP_KEY    = input("Enter your APP KEY: ")
APP_SECRET = input("Enter your APP SECRET: ")
AUTH_CODE  = input("Paste the Dropbox authorization code: ")

auth_header = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
res = requests.post(
    "https://api.dropbox.com/oauth2/token",
    data={
        "code":           AUTH_CODE,
        "grant_type":     "authorization_code",
        "redirect_uri":   "https://localhost"
    },
    headers={
        "Authorization":  f"Basic {auth_header}",
        "Content-Type":   "application/x-www-form-urlencoded"
    }
)

if res.ok:
    print("\nYour refresh token is:\n", res.json().get("refresh_token"))
else:
    print("Error:", res.text)
