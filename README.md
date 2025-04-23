# ComfyUI DropSend Node

This custom node package adds automatic Dropbox upload capabilities to your ComfyUI workflows.

## 🚀 Features

- **📤 Dropbox AutoUploader Node**
  - Monitors a specified folder (e.g., ComfyUI's `output/`) in real time
  - Automatically uploads new images to your Dropbox account

- **🛠️ Dropbox Setup Node**
  - Accepts your App Key, App Secret, and Authorization Code
  - Automatically generates a refresh token and saves credentials to a `.env` file

- **🔐 Helpers**
  - `generate_base64.py`: Easily generate your Base64 App credentials
  - `get_refresh_token.py`: Standalone CLI for manually retrieving a refresh token

---

## 🧩 Installation

Place this folder inside your `ComfyUI/custom_nodes/` directory:

```bash
ComfyUI/custom_nodes/ComfyUI_DropSendNode/
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🔧 Setup Instructions

1. Go to the [Dropbox App Console](https://www.dropbox.com/developers/apps) and create a new app.
2. Enable `App Folder` access and note your **App Key** and **App Secret**.
3. Generate an **Authorization Code** via:
   ```
   https://www.dropbox.com/oauth2/authorize?client_id=APPKEY&response_type=code&token_access_type=offline
   ```
4. Paste these into the **🛠️ Dropbox Setup** node and run it once.
5. Then use the **📤 Dropbox AutoUploader** node in your workflow to monitor and upload.

---

## ✅ Example Workflow
- Connect your image-saving pipeline to the default output folder
- Add the **📤 AutoUploader** node pointing to that folder
- Files will upload as soon as they’re saved

---

## 🧪 Tested On
- Python 3.10 / 3.11
- ComfyUI latest release (2024–2025)
- Dropbox API with refresh token support

---

## License
MIT
