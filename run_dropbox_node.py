# ComfyUI_DropSendNode/run_dropbox_node.py

import os
import threading
from dotenv import load_dotenv, dotenv_values
from .monitor_output import start_monitoring

class DropSendRunNode:
    @classmethod
    def INPUT_TYPES(cls):
        node_dir = os.path.dirname(__file__)
        env_path = os.path.join(node_dir, ".env")

        default_watch = os.path.join(os.getcwd(), "output")
        default_dest  = "/Apps/ComfyUI_Output_Files"

        # if .env exists, pull last-used folder
        if os.path.exists(env_path):
            cfg = dotenv_values(env_path)
            default_dest = cfg.get("DROPBOX_FOLDER", default_dest)

        return {
            "required": {
                "watch_folder":        ("STRING", {"default": default_watch}),
                "dropbox_dest_folder": ("STRING", {"default": default_dest}),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE   = True
    FUNCTION      = "start"

    def start(self, watch_folder, dropbox_dest_folder):
        # persist new destination into .env alongside secrets
        node_dir = os.path.dirname(__file__)
        env_path = os.path.join(node_dir, ".env")

        existing = {}
        if os.path.exists(env_path):
            existing = dotenv_values(env_path)

        existing["DROPBOX_FOLDER"] = dropbox_dest_folder
        with open(env_path, "w") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")

        load_dotenv(env_path, override=True)

        # start (or restart) the folder watcher
        thread = threading.Thread(
            target=start_monitoring,
            args=(watch_folder, dropbox_dest_folder),
            daemon=True
        )
        thread.start()

        return (
            f"📦✅ .env updated: DROPBOX_FOLDER={dropbox_dest_folder}",
            f"🔎📁 Monitoring Folder: {watch_folder} → {dropbox_dest_folder}"
        )

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropSendRunNode": DropSendRunNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropSendRunNode": "📦📤 Dropbox AutoUploader Run"}
