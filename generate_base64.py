# ComfyUI_DropSendNode/generate_base64.py

import base64

app_key    = input("Enter your App Key: ")
app_secret = input("Enter your App Secret: ")

credentials = f"{app_key}:{app_secret}"
encoded     = base64.b64encode(credentials.encode()).decode()
print(f"\nBasic {encoded}")
