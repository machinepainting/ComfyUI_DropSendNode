# ComfyUI DropSend Node

Want to automatically move your files off the cloud to your local machine? Want to do so securely with optional encryption? Well do I have the node for you!

DROPSEND NODE - A custom ComfyUI node for seamless Dropbox uploads with **optional** encryption capabilities. Automatically uploads your ComfyUI output files (images and videos) to Dropbox cloud storage — with or without encryption.

## 🔄 How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLOUD (RunPod, etc.)                                │
│                                                                             │
│      ComfyUI generates files ──→ DropSend Node ──→ Uploads to Dropbox       │
│        (png, mp4, etc.)         │                                           │
│                                 │                                           │
│                                 ▼                                           │
│                      ┌──────────────────────┐                               │
│                      │ Encryption OPTIONAL  │                               │
│                      │ ☐ OFF: file.png      │                               │
│                      │ ☑ ON:  file.png.enc  │                               │
│                      └──────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                               ☁️ DROPBOX
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           YOUR LOCAL MACHINE                                │
│                                                                             │
│   Dropbox syncs/downloads ──→ If encrypted: Run decrypt script (local)      │
│                                             ──→ file.png (viewable!)        │
│                                                                             │
│                               If not encrypted: Ready to use!               │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Encryption is completely optional.** If you don't need it, simply leave `enable_encryption` off and your files upload directly to Dropbox as-is. Enable encryption only if you want an extra layer of security for your files in cloud storage.

## 📤📦 Features

- **📤📦 DropSend AutoUploader Node**
Automatically uploads newly created files to Dropbox with optional file encryption capabilities.

- Monitors a specified folder (e.g., ComfyUI's `output/`) in real time, with optional recursive subfolder monitoring.
- Supports common ComfyUI file types: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.mp4`, `.avi`, `.mov`.
- Optional encryption of files before upload, creating `.enc` files using a secure Fernet key (AES-128).
- Configurable toggles for:
- `enable_encryption`: Encrypt files before upload (default: off).
- `Post_Delete_Enc`: Delete encrypted `.enc` files after upload verification (default: off).
- `Subfolder_Monitor`: Monitor subfolders in the watch directory (default: on).
- `run_process`: Start or stop the monitoring and uploading process (default: on).
- Uses a queue system to ensure reliable processing of files, even under high load, preventing skipped files.
- Verifies upload integrity using SHA256 checksums to ensure files are not corrupted during transfer.

- **🛠️📦 DropSend Setup Node**
Streamlines Dropbox API access setup and encryption key management.

- Accepts your App Key, App Secret, and Authorization Code to generate a refresh token.
- Provides API credentials and optional encryption key for easy integration into Environment Variables and RunPod Secrets.
- Supports two storage methods:
- `env_file`: Saves credentials to a `.env` file (recommended for local user setups).
- `display_only`: Displays credentials in the console for manual copying (recommended for cloud setups like RunPod).
- Supports three encryption key methods:
- `off`: No encryption key is generated (use if encryption is not needed).
- `Display Only`: Displays the encryption key in the console with other credentials.
- `save to .env`: Saves the encryption key to the `.env` file.
- Automatically runs curl to extend the lifespan of your API keys.

- **🔐📁 Standalone Decryption Scripts (Local Use Only)**
Decrypt `.enc` files on your local machine using the included scripts in the `/scripts/` folder.

- **Local use only** — Run these on your computer after downloading/syncing encrypted files from Dropbox (move files out of synced Dropbox local folder before decrypting, otherwise it defeats the purpose of using encryption.).
- Cross-platform support for macOS, Windows, and Linux.
- Restores encrypted files back to their original format (PNG, JPG, MP4, etc.).
- Supports recursive folder processing.
- Option to organize `.enc` files after decryption.
- Includes optional encryption scripts for manual local encryption (not needed for normal DropSend operation).

---

## 💾📦 Installation

Clone this repository into the `ComfyUI/custom_nodes/` directory:

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/machinepainting/ComfyUI_DropSendNode.git
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🔧📦 Dropbox Setup Instructions
1. Login to your Dropbox Account [Dropbox](https://www.dropbox.com/)(Ideally Dropbox is already setup and installed on your local.)
2. Go to the [Dropbox DBX Platform](https://www.dropbox.com/developers/). Select `Create Apps` Button to make a new app.
3. Click 'Scoped Access'. Enable `App Folder` access (reccommended) or `Full Dropbox` (only use full access if needed).
 
** Note: If you cannot select `App Folder`, the `Apps` folder likely does not exist or is not yet created in your Dropbox. Navigate to your Dropbox root directory and create the `/Apps/` **

4. Name your app and select `Create app` button. 
5. Navigate to the `Permissions` Tab. Check the box for the following options:

  Account Info
    - account_info.write
    - account_info.read
  Files and Folders
    - files.metadata.write
    - files.metadata.read
    - files.content.write
    - files.content.read

6. Click `Submit` to save permissions.
7. Navigate back to the `Settings` Tab.
8. Note your `App Key` and `App Secret` or be prepared to Copy and Paste into the 'DropSend Setup Node' in the next steps.

## 🏃‍♂️‍➡️🫛📦 DropSend Setup Node Instructions (Runpod & Cloud Users)
(Local Users Read Instructions below.)

9. Open the 'DropSend Setup Node' in your ComfyUI and Paste in the following credentials:

    - `app_key`                 [ paste app key here ]
    - `app_secret`              [ paste secret key here ]
    - `auth_code`               [ leave blank until next step ]
    - `dropbox_dest_folder`     [ /Apps/ComfyUI_Output_Files ] (Change the folder name if desired)
    - `reconnect`               [ false ] (Set to `true` only if you need to re-run or delete current credentials)
    - `storage_method`          [ display_only ] (Select `env_file` only if you want to store credentials in persistent storage or locally)

10. Click 'Run' on the node or in the ComfyUI workflow. Two Dropbox pop-up windows will appear to accept app permissions and generate the Authorization Code.
11. Copy the entire output string from the pop-up and paste it into the `auth_code` field in the DropSend Setup Node.
12. Click 'Run' again on the DropSend Setup Node. Open the bottom panel (Terminal) in ComfyUI or check your running terminal process to note the returned credentials. Example:

```bash
    DROPBOX_APP_KEY: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    DROPBOX_APP_SECRET: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    DROPBOX_REFRESH_TOKEN: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    comfyui_encryption_key=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX (only displays if encryption_key_method is 'true')
```

13. For Runpod users, navigate to the main dashboard at [https://www.runpod.io]. Click Secrets in the sidebar, then click Create Secret.
** Note: For other cloud services, follow their instructions to paste the credentials into the appropriate Environment Variables sections for App Keys, Secrets, API Keys, etc. **
 
14. Create three separate secrets on Runpod (Secret Names must match exactly as shown below). Copy the credentials from Step 12 into the corresponding fields:

1   Secret Name:  `DROPBOX_APP_KEY` Secret Value: `PASTE_YOUR_APP_KEY_HERE` 

2   Secret Name:  `DROPBOX_APP_SECRET` Secret Value: `PASTE_YOUR_APP_SECRET_HERE`

3   Secret Name:  `DROPBOX_REFRESH_TOKEN` Secret Value: `PASTE_YOUR_REFRESH_TOKEN_HERE`

4   Secret Name:  `comfyui_encryption_key` Secret Value: `PASTE_YOUR_ENCRYPTION_KEY_HERE`


15. Add the Environment Variables to your Runpod Pod. (Recommended: Create a custom template so you only have to do this once.) If not using a custom template, Before deploying your pod, select `Edit Template` and select `Environment Variables` (Dropdown). Click `+ Add Environment Variables` and add the following:

1 - Click `key` and paste in `DROPBOX_APP_KEY` then click the `🗝️` symbol in the `value` field and select `DROPBOX_APP_KEY`. The field should now read `{{ RUNPOD_SECRET_DROPBOX_APP_KEY }}`

2 - Click `key` and paste in `DROPBOX_APP_SECRET` then click the `🗝️` symbol in the `value` field and select `DROPBOX_APP_SECRET`. The field should now read `{{ RUNPOD_SECRET_DROPBOX_APP_SECRET }}`

3 - Click `key` and paste in `DROPBOX_REFRESH_TOKEN` then click the `🗝️` symbol in the `value` field and select `DROPBOX_REFRESH_TOKEN`. The field should now read `{{ RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN }}`

4 - Click `key` and paste in `comfyui_encryption_key` then click the `🗝️` symbol in the `value` field and select `comfyui_encryption_key`. The field should now read `{{ RUNPOD_SECRET_comfyui_encryption_key }}`

16. Click `Set Overrides`, then deploy your Pod
** Note: for non-Runpod/other cloud users: Input Environment Variables as required, ensuring they are named correctly; `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`,`comfyui_encryption_key`

17. Add the DropSend AutoUploader Node to your ComfyUI workflow, configure settings (e.g., enable_encryption, Subfolder_Monitor, run_process), and run. Verify that files are uploaded to your Dropbox folder.

Note: If you change dropbox_dest_folder, it must start with /Apps/ for App Folder access.
Stopping the Process: Set run_process to False and run the node to stop monitoring and uploading without restarting ComfyUI. 

ENJOY!!

## 🛠️💻📦 DropSend Setup Node Instructions (Local Computer Users or .env Preference)
(Runpod or cloud users can use a .env file for a simplified setup, but saving API keys and secrets in a .env file on the cloud is not recommended for security reasons. This is standard for local users.)

9b. Open the 'DropSend Setup Node' in your ComfyUI and Paste in the following credentials:

    - `app_key`                 [ paste app key here ]
    - `app_secret`              [ paste secret key here ]
    - `auth_code`               [ leave blank until next step ]
    - `dropbox_dest_folder`     [ /Apps/ComfyUI_Output_Files ] (Change the folder name if desired)
    - `reconnect`               [ false ] (Set to `true` only if you need to re-run or delete current credentials)
    - `storage_method`          [ env_file ] (Stores credentials in persistent or local storage)
    - `encryption_key_method`   [Display Only] (or save to .env for local storage, off if encryption is not needed)
    
10b. Click 'Run' on the node or in the ComfyUI workflow. Two Dropbox pop-up windows will appear to accept app permissions and generate the Authorization Code.
11b. Copy the entire output string from the pop-up and paste it into the `auth_code` field in the DropSend Setup Node.
12b. Click 'Run' again on the DropSend Setup Node. Restart ComfyUI.
13b. Open your ComfyUI workflow and add the `DropSend AutoUploader Node` to your workflow. You can now remove the DropSend Setup Node from your workflow. Run ComfyUI and confirm that media is being sent to your Dropbox folder. Restart ComfyUI to load the .env file (if used). 

Note: If you change the `dropbox_dest_folder` in the node settings, it will automatically create a new folder in Dropbox as long as it starts with `/Apps/`.

ENJOY!!

---

## 🔑📦 Encryption Key Management

If you enable encryption in the DropSend AutoUploader Node, an encryption key is generated during setup (unless `encryption_key_method` is `off`). This key is **required** to decrypt `.enc` files downloaded from Dropbox.

### Saving the Encryption Key

**Display Only (Recommended for Cloud):**

If `encryption_key_method` is `Display Only`, the key is shown in the console after running the setup node with a valid `auth_code`:

```
comfyui_encryption_key=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Copy the key and store it securely using one of the methods below.

**Save to .env (Recommended for Local Only, NOT CLOUD USERS!):**

If `encryption_key_method` is `save to .env`, the key is saved in `ComfyUI/custom_nodes/ComfyUI_DropSendNode/.env` as:

```
comfyui_encryption_key=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Ensure the `.env` file is excluded from version control (add to `.gitignore`).

---

## 🔐📁 Standalone Decryption Scripts (Local Use Only)

The `/scripts/` folder contains standalone scripts to decrypt files on your **local machine**.

> ⚠️ **These scripts are for LOCAL USE ONLY.** Run them on your personal computer after downloading or syncing encrypted files from Dropbox. Do not run on cloud instances.

> 💡 **Universal Compatibility:** These scripts work with both DropSend (Dropbox) and DriveSend (Google Drive) nodes. They use the same encryption key (`comfyui_encryption_key`), so you only need to set up key storage once.

### What Are These Scripts For?

**Decryption Scripts** — The primary scripts. Use these on your local machine to decrypt `.enc` files you've downloaded/synced from Dropbox. When encryption is enabled in the DropSend node, your files are uploaded as encrypted `.enc` files. These scripts restore them to their original format so you can view and use them.

**Encryption Scripts** — Optional utility scripts. You do NOT need these for normal DropSend operation—the node handles encryption automatically during upload. These are provided for users who want to manually encrypt local files for backup or other purposes using the same key.

### Supported File Types

The scripts support all formats the DropSend node handles:
- Images: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`
- Videos: `.mp4`, `.avi`, `.mov`

When decrypting, the original file extension is preserved (e.g., `video.mp4.enc` → `video.mp4`).

### Prerequisites (All Platforms)

**Python 3.8+** and the **cryptography** library are required:

```bash
pip install cryptography
```

---

## 🍎 macOS Setup & Usage

### Storing Your Encryption Key in Keychain

1. Open **Keychain Access** (search in Spotlight)
2. Click **File > New Password Item**
3. Fill in the fields:
   - **Keychain Item Name:** `ComfyUI_Encryption_Key`
   - **Account Name:** `ComfyUI`
   - **Password:** Paste your encryption key
4. Click **Add**

To retrieve later: Search for `ComfyUI_Encryption_Key` in Keychain Access, double-click, check **Show Password**, and authenticate.

### Running the Scripts

1. Navigate to the scripts folder:
   ```bash
   cd ComfyUI/custom_nodes/ComfyUI_DropSendNode/scripts
   ```

2. Make the script executable (first time only):
   ```bash
   chmod +x decrypt_folder_mac.sh
   chmod +x encrypt_folder_mac.sh
   ```

3. Run the decryption script:
   ```bash
   ./decrypt_folder_mac.sh
   ```

4. When prompted:
   - Drag and drop the folder containing `.enc` files into the terminal, or type the path
   - Choose whether to process subfolders recursively (Y/N)
   - Optionally move `.enc` files to a separate folder after decryption

---

## 🪟 Windows Setup & Usage

### Storing Your Encryption Key

**Using Environment Variable (Recommended):**

1. Press `Win + R`, type `sysdm.cpl`, press Enter
2. Go to **Advanced** tab → **Environment Variables**
3. Under **User variables**, click **New**
4. Set:
   - **Variable name:** `COMFYUI_ENCRYPTION_KEY`
   - **Variable value:** Your encryption key
5. Click **OK** to save
6. Restart any open terminals/command prompts

### Running the Scripts

1. Open **Command Prompt** or **PowerShell**

2. Navigate to the scripts folder:
   ```cmd
   cd ComfyUI\custom_nodes\ComfyUI_DropSendNode\scripts
   ```

3. Run the decryption script:
   ```cmd
   python decrypt_folder_win.py
   ```

4. When prompted:
   - Enter the full path to the folder containing `.enc` files
   - Choose whether to process subfolders recursively (Y/N)
   - Optionally move `.enc` files to a separate folder after decryption

---

## 🐧 Linux Setup & Usage

### Storing Your Encryption Key

**Option A: Environment Variable (Recommended)**

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
export COMFYUI_ENCRYPTION_KEY="your_encryption_key_here"
```

Then reload:

```bash
source ~/.bashrc
```

**Option B: Secret Service (GNOME Keyring / KWallet)**

If you have `secret-tool` installed (comes with `libsecret-tools`):

```bash
# Store the key
echo -n "your_encryption_key_here" | secret-tool store --label="ComfyUI Encryption Key" service ComfyUI username ComfyUI

# Retrieve the key (for verification)
secret-tool lookup service ComfyUI username ComfyUI
```

Install secret-tool if needed:

```bash
# Debian/Ubuntu
sudo apt install libsecret-tools

# Fedora
sudo dnf install libsecret

# Arch
sudo pacman -S libsecret
```

### Running the Scripts

1. Navigate to the scripts folder:
   ```bash
   cd ComfyUI/custom_nodes/ComfyUI_DropSendNode/scripts
   ```

2. Make the script executable (first time only):
   ```bash
   chmod +x decrypt_folder_linux.sh
   chmod +x encrypt_folder_linux.sh
   ```

3. Run the decryption script:
   ```bash
   ./decrypt_folder_linux.sh
   ```

4. When prompted:
   - Enter the full path to the folder containing `.enc` files
   - Choose whether to process subfolders recursively (Y/N)
   - Optionally move `.enc` files to a separate folder after decryption

---

## 🔄 Cross-Platform Python Script (Alternative)

For maximum compatibility, use the Python script directly on any platform:

```bash
cd ComfyUI/custom_nodes/ComfyUI_DropSendNode/scripts
python decrypt_folder.py
```

This script will:
1. Automatically detect your operating system
2. Check for your encryption key (environment variable, Keychain, or Secret Service)
3. Prompt for the key if not found
4. Process all `.enc` files and restore them to their original format

---

## 🛠️📦 DropSend Setup Instructions (Manual Setup)(Advanced)
(Only use this method if you choose to setup manually. This method is for advanced users and does not use the `DropSend Setup Node`.)

1c. Follow the "Dropbox Setup Instructions" Above to build the app in Dropbox and access the `App Key` and `App Secret`. 

2c. Use the following URL and replace `APPKEYHERE` with your `App_Key`:
https://www.dropbox.com/oauth2/authorize?client_id=APPKEYHERE&response_type=code&token_access_type=offline

3c. Open Terminal and run the following curl with your credentials input in the correct fields:

    curl https://api.dropbox.com/oauth2/token \
    -d code=AUTHORIZATIONCODEHERE \
    -d grant_type=authorization_code \
    -u APPKEYHERE:APPSECRETHERE
    
4c. Copy and note the returned refresh token and use it in your cloud or local environment variables where applicable. 

ENJOY!!

---

## ⚠️ Security Best Practices

1. **Never commit your `.env` file** - Ensure `.env` is in your `.gitignore`
2. **Use secure key storage** - Prefer OS-native credential storage (Keychain, Environment Variables, Secret Service) over plain text files
3. **Backup your encryption key** - Without it, encrypted files cannot be recovered
4. **Use unique keys** - Don't reuse the encryption key for other purposes

---

## ⚠️ Important Notes

### Using Both DropSend and DriveSend

If you use both nodes (DropSend for Dropbox and [DriveSend](https://github.com/machinepainting/ComfyUI_DriveSendNode) for Google Drive), you only need to store your encryption key **once** using any of the methods above. The scripts check for multiple key names for backward compatibility:

- `COMFYUI_ENCRYPTION_KEY` (recommended)
- `comfyui_encryption_key`
- `DROPSEND_ENCRYPTION_KEY` (legacy)
- `DRIVESEND_ENCRYPTION_KEY` (legacy)

The same applies to Keychain/Secret Service - the scripts will find your key regardless of which name you used.

### Running Both Nodes Simultaneously

If you have both DropSend and DriveSend installed and want to use them at the same time, configure them to watch **different folders** to avoid conflicts. For example:

- DropSend watches: `ComfyUI/output/dropbox/`
- DriveSend watches: `ComfyUI/output/gdrive/`

Or simply use one node at a time by setting `run_process` to `False` on the node you're not using.

---

## 🧪 Tested On

**Fully Tested:**
- macOS 13+ (Ventura, Sonoma)
- Python 3.10 / 3.11
- ComfyUI (Jan 2026)
- Dropbox API with refresh token support

**Community Testing Needed:**
- Windows 10/11 — *Please test and report any issues or suggestions!*
- Linux (Ubuntu, Fedora, Arch) — *Please test and report any issues or suggestions!*

If you encounter any problems on Windows or Linux, please open an issue on GitHub with:
- Your OS version
- Python version
- Error messages (if any)
- Steps to reproduce

Contributions and pull requests are welcome!

Shout-out to Adam for his contributions to this node build and additional Dropbox assistant tool, he helped make the tedious setup easier!

---

## 📁 Repository Structure

```
ComfyUI_DropSendNode/
├── __init__.py
├── dropsend_uploader_node.py
├── dropsend_setup_node.py
├── dropbox_upload.py
├── dropbox_auth_manager.py
├── encrypt_file.py
├── monitor_output.py
├── oauth_handler.py
├── requirements.txt
├── README.md
├── .gitignore
└── scripts/
    ├── decrypt_folder.py          # Cross-platform Python script (recommended)
    ├── decrypt_folder_mac.sh      # macOS decryption script
    ├── encrypt_folder_mac.sh      # macOS encryption script (local use only)
    ├── decrypt_folder_win.py      # Windows decryption script
    ├── encrypt_folder_win.py      # Windows encryption script (local use only)
    ├── decrypt_folder_linux.sh    # Linux decryption script
    └── encrypt_folder_linux.sh    # Linux encryption script (local use only)
```

---

## License
MIT
