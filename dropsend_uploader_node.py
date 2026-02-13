# dropsend_uploader_node.py

import os
import threading
import logging
import time
from dotenv import load_dotenv, dotenv_values
from watchdog.observers import Observer
from .monitor_output import start_monitoring, watcher_observer, stop_queue_processor
from .encrypt_file import FileEncryptHandler, ENCRYPT_EXTENSIONS, stop_queue_processor as stop_encrypt_queue_processor, get_encryption_key

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dropsend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define encrypt_observer at module level
encrypt_observer = None

class DropSendAutoUploaderNode:
    @classmethod
    def INPUT_TYPES(cls):
        node_dir = os.path.dirname(__file__)
        env_path = os.path.join(node_dir, ".env")

        default_watch = os.path.join(os.getcwd(), "output")
        default_dest = "/Apps/ComfyUI_Output_Files"
        default_encrypt = True
        default_delete_enc = False
        default_subfolder_monitor = True
        default_run_process = True

        if os.path.exists(env_path):
            cfg = dotenv_values(env_path)
            default_dest = cfg.get("DROPBOX_FOLDER", default_dest)
            default_encrypt = cfg.get("ENABLE_ENCRYPTION", "False").lower() == "true"
            default_delete_enc = cfg.get("POST_DELETE_ENC", "False").lower() == "true"
            default_subfolder_monitor = cfg.get("SUBFOLDER_MONITOR", "True").lower() == "true"
            default_run_process = cfg.get("RUN_PROCESS", "True").lower() == "true"

        return {
            "required": {
                "watch_folder": ("STRING", {"default": default_watch}),
                "dropbox_dest_folder": ("STRING", {"default": default_dest}),
                "enable_encryption": ("BOOLEAN", {"default": default_encrypt}),
                "Post_Delete_Enc": ("BOOLEAN", {"default": default_delete_enc}),
                "Subfolder_Monitor": ("BOOLEAN", {"default": default_subfolder_monitor}),
                "run_process": ("BOOLEAN", {"default": default_run_process, "label": "Run Process"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "start"

    def start(self, watch_folder, dropbox_dest_folder, enable_encryption, Post_Delete_Enc, Subfolder_Monitor, run_process):
        global encrypt_observer
        logger.info(f"Starting DropSend AutoUploader: watch_folder={watch_folder}, dropbox_dest_folder={dropbox_dest_folder}, encryption={enable_encryption}, Post_Delete_Enc={Post_Delete_Enc}, Subfolder_Monitor={Subfolder_Monitor}, run_process={run_process}")

        # Handle stopping the process if run_process is False
        if not run_process:
            logger.info("Stopping DropSend AutoUploader monitoring")
            if watcher_observer and watcher_observer.is_alive():
                watcher_observer.stop()
                watcher_observer.join()
                logger.info("Upload watcher stopped")
            if encrypt_observer and encrypt_observer.is_alive():
                encrypt_observer.stop()
                encrypt_observer.join()
                logger.info("Encryption watcher stopped")
            # Stop queue processors
            stop_queue_processor()  # Stop upload queue processor
            stop_encrypt_queue_processor()  # Stop encryption queue processor
            # Print confirmation message to console
            stop_message = f"""
=====================================================================
📦🛑 DropSend - AutoUploader - RunProcess STOPPED
=====================================================================
All monitoring, uploading, and encryption processes for {watch_folder} have been stopped.
Set 'run_process' to True and run the node again to resume.
=====================================================================
"""
            print(stop_message)
            logger.info(stop_message)
            return (f"All monitoring, uploading, and encryption stopped for {watch_folder}",)

        # Validate watch_folder
        if not os.path.exists(watch_folder):
            logger.error(f"Watch folder does not exist: {watch_folder}")
            raise ValueError(f"Watch folder does not exist: {watch_folder}")
        if not os.path.isdir(watch_folder):
            logger.error(f"Watch folder is not a directory: {watch_folder}")
            raise ValueError(f"Watch folder is not a directory: {watch_folder}")

        # Validate Dropbox credentials
        from .dropbox_upload import get_token
        try:
            get_token()
        except Exception as e:
            logger.error(f"Invalid Dropbox credentials: {str(e)}")
            raise ValueError(f"Invalid Dropbox credentials: {str(e)}")

        # Validate encryption key if enabled
        if enable_encryption:
            ENCRYPT_KEY = get_encryption_key()
            if not ENCRYPT_KEY:
                logger.error("Encryption enabled but no encryption key found")
                raise ValueError(f"Encryption enabled but no encryption key found. Set COMFYUI_ENCRYPTION_KEY environment variable.")

        # Persist settings
        node_dir = os.path.dirname(__file__)
        env_path = os.path.join(node_dir, ".env")

        existing = {}
        if os.path.exists(env_path):
            existing = dotenv_values(env_path)

        existing["DROPBOX_FOLDER"] = dropbox_dest_folder
        existing["ENABLE_ENCRYPTION"] = str(enable_encryption)
        existing["POST_DELETE_ENC"] = str(Post_Delete_Enc)
        existing["SUBFOLDER_MONITOR"] = str(Subfolder_Monitor)
        existing["RUN_PROCESS"] = str(run_process)
        with open(env_path, "w") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")

        load_dotenv(env_path, override=True)

        # Start processes only if run_process is True
        if run_process:
            # Start folder watcher
            thread = threading.Thread(
                target=start_monitoring,
                args=(watch_folder, dropbox_dest_folder, enable_encryption, Post_Delete_Enc, Subfolder_Monitor),
                daemon=True
            )
            thread.start()

            # Start encryption watcher if enabled
            if enable_encryption:
                encrypt_handler = FileEncryptHandler(watch_folder, False, Subfolder_Monitor)
                encrypt_observer = Observer()
                encrypt_observer.schedule(encrypt_handler, watch_folder, recursive=Subfolder_Monitor)
                encrypt_observer.start()
                logger.info(f"Starting encryption monitor for {watch_folder}")

                def keep_encrypt_alive():
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        if encrypt_observer:
                            encrypt_observer.stop()
                    if encrypt_observer:
                        encrypt_observer.join()

                threading.Thread(target=keep_encrypt_alive, daemon=True).start()

        return (f"📦✅ .env updated: DROPBOX_FOLDER={dropbox_dest_folder}, ENABLE_ENCRYPTION={enable_encryption}, POST_DELETE_ENC={Post_Delete_Enc}, SUBFOLDER_MONITOR={Subfolder_Monitor}, RUN_PROCESS={run_process}",)

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropSendAutoUploader": DropSendAutoUploaderNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropSendAutoUploader": "📦📤 DropSend - AutoUploader"}
