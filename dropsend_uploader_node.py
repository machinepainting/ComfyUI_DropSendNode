# dropsend_uploader_node.py

import os
import threading
import logging
import time
from datetime import date, datetime
from dotenv import load_dotenv, dotenv_values
from watchdog.observers import Observer
from .monitor_output import start_monitoring, watcher_observer, stop_queue_processor
from .encrypt_file import FileEncryptHandler, ENCRYPT_EXTENSIONS, stop_queue_processor as stop_encrypt_queue_processor, get_encryption_key
from .safe_paths import resolve_safe_watch_folder, validate_dropbox_dest, get_output_root

# Folder format options. The first option uses the user's literal
# text as a project folder name (no date appended); the remaining
# options append today's date to the user's base folder in the
# selected style. Date formats use "-" or "." as separators rather
# than "/" so the date stays within a single path segment, which
# keeps _strip_trailing_date simple and avoids visually splitting
# the date across folders.
PROJECT_NAME_FORMAT = "project_name"
DATE_FORMATS = {
    "mm-dd-yyyy": "%m-%d-%Y",
    "dd-mm-yyyy": "%d-%m-%Y",
    "yyyy-mm-dd": "%Y-%m-%d",
    "dd.mm.yyyy": "%d.%m.%Y",
    "yyyy.mm.dd": "%Y.%m.%d",
}
FOLDER_FORMAT_OPTIONS = [PROJECT_NAME_FORMAT] + list(DATE_FORMATS.keys())
DEFAULT_FOLDER_FORMAT = PROJECT_NAME_FORMAT


def _today_str(format_name):
    fmt = DATE_FORMATS.get(format_name)
    if not fmt:
        return ""
    return date.today().strftime(fmt)


def _strip_trailing_date(path, format_name):
    """If the last `/`-separated segment of `path` parses as a date in
    the given format, return `path` with that segment removed. Otherwise
    return `path` unchanged. Used to recover the BASE folder from a
    persisted destination that already has a date appended."""
    fmt = DATE_FORMATS.get(format_name)
    if not fmt:
        return path
    cleaned = path.rstrip("/")
    parts = cleaned.split("/")
    if len(parts) < 2:
        return path
    try:
        datetime.strptime(parts[-1], fmt)
    except ValueError:
        return path
    return "/".join(parts[:-1]) or "/"

# Logging configured by the package __init__ — see __init__.py.
logger = logging.getLogger(__name__)

# Define encrypt_observer at module level
encrypt_observer = None

class DropSendAutoUploaderNode:
    @classmethod
    def INPUT_TYPES(cls):
        node_dir = os.path.dirname(__file__)
        env_path = os.path.join(node_dir, ".env")

        default_watch = get_output_root()
        default_dated_base = "/ComfyUI_Output_Files"
        default_flat_base = "/ComfyUI-Project/My-Project"
        default_encrypt = True
        default_delete_enc = False
        default_subfolder_monitor = True
        default_run_process = True
        default_folder_format = DEFAULT_FOLDER_FORMAT

        if os.path.exists(env_path):
            cfg = dotenv_values(env_path)
            # Two persisted bases let the dated and project-name modes
            # each remember their own folder pattern, so switching the
            # dropdown doesn't lose whichever setup the user isn't
            # currently using. Legacy fallback chain on the dated key
            # picks up destinations configured by the Setup Node or a
            # prior version of this node.
            default_dated_base = cfg.get(
                "DROPBOX_FOLDER_BASE_DATED",
                cfg.get("DROPBOX_FOLDER_BASE", cfg.get("DROPBOX_FOLDER", default_dated_base)),
            )
            default_flat_base = cfg.get("DROPBOX_FOLDER_BASE_FLAT", default_flat_base)
            default_encrypt = cfg.get("ENABLE_ENCRYPTION", "False").lower() == "true"
            default_delete_enc = cfg.get("POST_DELETE_ENC", "False").lower() == "true"
            default_subfolder_monitor = cfg.get("SUBFOLDER_MONITOR", "True").lower() == "true"
            default_run_process = cfg.get("RUN_PROCESS", "True").lower() == "true"
            default_folder_format = cfg.get("DROPBOX_FOLDER_FORMAT", default_folder_format)
            if default_folder_format not in FOLDER_FORMAT_OPTIONS:
                default_folder_format = DEFAULT_FOLDER_FORMAT

        if default_folder_format == PROJECT_NAME_FORMAT:
            default_dest = default_flat_base
        else:
            # Defensive: strip a trailing date in case a legacy
            # DROPBOX_FOLDER value already had one appended.
            default_dated_base = _strip_trailing_date(default_dated_base, default_folder_format)
            default_dest = default_dated_base.rstrip("/") + "/" + _today_str(default_folder_format)

        return {
            "required": {
                "watch_folder": ("STRING", {"default": default_watch}),
                "dropbox_dest_folder": ("STRING", {"default": default_dest}),
                "folder_format": (FOLDER_FORMAT_OPTIONS, {"default": default_folder_format}),
                "enable_encryption": ("BOOLEAN", {"default": default_encrypt}),
                "Post_Delete_Enc": ("BOOLEAN", {"default": default_delete_enc}),
                "Subfolder_Monitor": ("BOOLEAN", {"default": default_subfolder_monitor}),
                "run_process": ("BOOLEAN", {"default": default_run_process, "label": "Run Process"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "start"

    def start(self, watch_folder, dropbox_dest_folder, folder_format, enable_encryption, Post_Delete_Enc, Subfolder_Monitor, run_process):
        global encrypt_observer

        # Resolve the actual destination at run-time. For date formats
        # this refreshes the date on every workflow run, so a saved
        # workflow opened yesterday still uploads into today's folder.
        # For project_name we use the user's literal text verbatim and
        # persist it as-is.
        if folder_format not in FOLDER_FORMAT_OPTIONS:
            folder_format = DEFAULT_FOLDER_FORMAT
        if folder_format == PROJECT_NAME_FORMAT:
            dated_base = None
            flat_base = dropbox_dest_folder
        else:
            dated_base = _strip_trailing_date(dropbox_dest_folder, folder_format)
            dropbox_dest_folder = dated_base.rstrip("/") + "/" + _today_str(folder_format)
            flat_base = None

        logger.info(f"Starting DropSend AutoUploader: watch_folder={watch_folder}, dropbox_dest_folder={dropbox_dest_folder}, folder_format={folder_format}, encryption={enable_encryption}, Post_Delete_Enc={Post_Delete_Enc}, Subfolder_Monitor={Subfolder_Monitor}, run_process={run_process}")

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

        # Constrain watch_folder to the ComfyUI output directory tree. The
        # uploader runs a recursive Watchdog observer that uploads every file
        # it sees, so an unrestricted path turns this node into an
        # arbitrary-file-read primitive on remotely-accessible ComfyUI hosts.
        try:
            watch_folder = resolve_safe_watch_folder(watch_folder)
        except ValueError as e:
            logger.error(str(e))
            raise

        if not os.path.isdir(watch_folder):
            logger.error(f"Watch folder is not a directory: {watch_folder}")
            raise ValueError(f"Watch folder is not a directory: {watch_folder}")

        try:
            dropbox_dest_folder = validate_dropbox_dest(dropbox_dest_folder)
        except ValueError as e:
            logger.error(str(e))
            raise

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

        # DROPBOX_FOLDER is the resolved destination (with date when a
        # date format is selected) for visibility and for any other
        # tool reading the .env. The two _BASE keys are written
        # independently — only the one matching the active format is
        # touched, so the other mode's saved pattern survives a switch.
        existing["DROPBOX_FOLDER"] = dropbox_dest_folder
        if dated_base is not None:
            existing["DROPBOX_FOLDER_BASE_DATED"] = dated_base
        if flat_base is not None:
            existing["DROPBOX_FOLDER_BASE_FLAT"] = flat_base
        existing["DROPBOX_FOLDER_FORMAT"] = folder_format
        existing["ENABLE_ENCRYPTION"] = str(enable_encryption)
        existing["POST_DELETE_ENC"] = str(Post_Delete_Enc)
        existing["SUBFOLDER_MONITOR"] = str(Subfolder_Monitor)
        existing["RUN_PROCESS"] = str(run_process)
        # Race-free open: the file is created with mode 0600 from the
        # start. The merged file may include DROPBOX_REFRESH_TOKEN /
        # COMFYUI_ENCRYPTION_KEY the user previously stored, so the
        # window between create-with-default-perms and a follow-up
        # chmod is exactly what we need to avoid.
        fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")

        load_dotenv(env_path, override=True)

        # Start processes only if run_process is True
        if run_process:
            # Build the encrypt handler up-front; start_monitoring will
            # schedule it on the SAME Observer as the upload handler.
            # macOS's _fsevents library refuses two separate watches on
            # the same path (the second emitter dies with "already
            # scheduled" and never delivers events), so we share one
            # Observer with multiple handlers.
            encrypt_handler = None
            if enable_encryption:
                encrypt_handler = FileEncryptHandler(watch_folder, False, Subfolder_Monitor)

            # Run synchronously — Observer manages its own threads, so
            # there is nothing to gain from wrapping this in a thread,
            # and a thread introduces a startup race where the upload
            # observer might not be ready before the first file lands.
            start_monitoring(
                watch_folder,
                dropbox_dest_folder,
                enable_encryption,
                Post_Delete_Enc,
                Subfolder_Monitor,
                encrypt_handler=encrypt_handler,
            )

            if encrypt_handler is not None:
                logger.info(f"Starting encryption monitor for {watch_folder}")

        # Build a banner the user sees in the node's UI output and in
        # the ComfyUI console. Each setting line is `key = value
        # (plain-English meaning)` so the implications are obvious at
        # a glance — no jumping back to the README to figure out what
        # POST_DELETE_ENC does.
        sub_desc = "subfolders watched recursively" if Subfolder_Monitor else "only the top-level folder is watched"
        if folder_format == PROJECT_NAME_FORMAT:
            fmt_desc = "your dropbox_dest_folder is used verbatim, e.g. /ComfyUI-Project/My-Project"
        else:
            fmt_desc = f"today's date in {folder_format} appended daily, folder refreshes each session"
        enc_desc = "files encrypted (.enc) before upload" if enable_encryption else "files uploaded as-is, no encryption"
        if enable_encryption:
            del_desc = ".enc files deleted after upload verifies" if Post_Delete_Enc else ".enc files kept on disk after upload"
        else:
            del_desc = "ignored — only matters when enable_encryption is true"

        banner = f"""
=====================================================================
📦📤 DropSend - AutoUploader - RUNNING
=====================================================================

Watching:
  {watch_folder}

Uploading to:
  {dropbox_dest_folder}

Settings:
  enable_encryption  = {str(enable_encryption).lower()} ({enc_desc})
  folder_format      = {folder_format} ({fmt_desc})
  Post_Delete_Enc    = {str(Post_Delete_Enc).lower()} ({del_desc})
  Subfolder_Monitor  = {str(Subfolder_Monitor).lower()} ({sub_desc})
  run_process        = {str(run_process).lower()} (monitoring active — set false and re-run to stop)

How to change settings while running:
  • Edit any field on this node and re-run the workflow to apply.
  • To switch from a date format to a project name: pick `project_name`
    in folder_format, edit dropbox_dest_folder to your project name,
    then re-run.
  • To stop monitoring entirely: set run_process = false and re-run.

=====================================================================
"""
        print(banner)
        logger.info(banner)
        return (banner,)

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropSendAutoUploader": DropSendAutoUploaderNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropSendAutoUploader": "📦📤 DropSend - AutoUploader"}
