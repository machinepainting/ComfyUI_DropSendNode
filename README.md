# ComfyUI DropSend Node

This custom node package enhances ComfyUI workflows with seamless Dropbox upload functionality. It streamlines uploading ComfyUI output files to your Dropbox cloud storage. To access these files locally, configure the Dropbox app to sync them to your computer.

## 📤📦 Features

- **📤📦 Dropbox AutoUploader Node**
  Automatically uploads newly created images/videos to Dropbox.

  - Monitors a specified folder (e.g., ComfyUI's `output/`) in real time.
  - Automatically uploads new files (images or video) to your Dropbox account.

- **🛠️📦 DropSend Setup Node**
  Streamlines Dropbox API access setup by reducing steps and automatically running curl to extend the lifespan of your API keys.   

  - Accepts your App Key, App Secret, and Authorization Code
  - Automatically generates a refresh token.
  - Provides API Key credentials for easy integration into your system's Environment Variables or Secret Keys.
  - (Optional) Saves credentials to a `.env` file if selected or if running locally.

---

## 💾📦 Installation

Clone this repository into the `ComfyUI/custom_nodes/` directory:

```bash
ComfyUI/custom_nodes/ComfyUI_DropSendNode/
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

6. Click `Submit` to save your selection.
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
```

13. For Runpod users, navigate to the main dashboard at [https://www.runpod.io]. Click Secrets in the sidebar, then click Create Secret.
** Note: For other cloud services, follow their instructions to paste the credentials into the appropriate Environment Variables sections for App Keys, Secrets, API Keys, etc. **
 
14. Create three separate secrets on Runpod (Secret Names must match exactly as shown below). Copy the credentials from Step 12 into the corresponding fields:

1   Secret Name:  `DROPBOX_APP_KEY` Secret Value: `PASTE_YOUR_APP_KEY_HERE` 

2   Secret Name:  `DROPBOX_APP_SECRET` Secret Value: `PASTE_YOUR_APP_SECRET_HERE`

3   Secret Name:  `DROPBOX_REFRESH_TOKEN` Secret Value: `PASTE_YOUR_REFRESH_TOKEN_HERE`


15. Add the Environment Variables to your Runpod Pod. You can do this by restarting, terminating, editing, or recreating your Pod. Before deploying, select `Edit Template` and select `Environment Variables` (Dropdown). Click `+ Add Environment Variables` and add the following:

1 - Click `key` and paste in `DROPBOX_APP_KEY` then click the `🗝️` symbol in the `value` field and select `DROPBOX_APP_KEY`. The field should now read `{{ RUNPOD_SECRET_DROPBOX_APP_KEY }}`

2 - Click `key` and paste in `DROPBOX_APP_SECRET` then click the `🗝️` symbol in the `value` field and select `DROPBOX_APP_SECRET`. The field should now read `{{ RUNPOD_SECRET_DROPBOX_APP_SECRET }}`

3 - Click `key` and paste in `DROPBOX_REFRESH_TOKEN` then click the `🗝️` symbol in the `value` field and select `DROPBOX_REFRESH_TOKEN`. The field should now read `{{ RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN }}`

16. Click `Set Overrides`, then deploy your Pod
** Note: for non-Runpod/other cloud users: Input Environment Variables as required, ensuring they are named correctly; `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`.

17. Open your ComfyUI workflow and add the the `DropSend AutoUploader Node` into your workflow. You can now remove the DropSend Setup Node from your workflow. Run ComfyUI and confirm that media is being sent to your Dropbox folder.
Note: If you change the `dropbox_dest_folder` in the node settings, it will automatically create a new folder in Dropbox as long as it starts with `/Apps/`.

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

10b. Click 'Run' on the node or in the ComfyUI workflow. Two Dropbox pop-up windows will appear to accept app permissions and generate the Authorization Code.
11b. Copy the entire output string from the pop-up and paste it into the `auth_code` field in the DropSend Setup Node.
12b. Click 'Run' again on the DropSend Setup Node. Restart ComfyUI.
13b. Open your ComfyUI workflow and add the `DropSend AutoUploader Node` to your workflow. You can now remove the DropSend Setup Node from your workflow. Run ComfyUI and confirm that media is being sent to your Dropbox folder.
Note: If you change the `dropbox_dest_folder` in the node settings, it will automatically create a new folder in Dropbox as long as it starts with `/Apps/`.

ENJOY!!

## 🛠️📦 DropSend Setup Instructions (Manual Setup)(Advanced)
(Only use this method if you choose to setup manually. This method is for advanced users and does not use the `DropSend Setup Node`.)

1c. Follow the "Dropbox Setup Instructions" Above to build the app in Dropbox and access the `App Key` and `App Secret`. 

2c. Use the following URL and replace `APPKEYHERE` with your `App_Key`:
https://www.dropbox.com/oauth2/authorize?client_id=APPKEYHERE&response_type=code&token_access_type=offline

3c. Open Terminal and run the following curl with your credentials input in the correct fields:

    curl https://api.dropbox.com/oauth2/token \
    -d code=AUTHORIZATIONCODEHERE \
    -d grant_type=authorization_code \
    -u APPKEYHERE:APPSECRETHERE`
    
4c. Copy and note the returned refresh token and use it in your cloud or local environment variables where applicable. 

ENJOY!!

## 🧪 Tested On
- Python 3.10 / 3.11
- ComfyUI (Aug 2025)
- Dropbox API with refresh token support

---

## License
MIT
