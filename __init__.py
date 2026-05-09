# ComfyUI_DropSendNode/__init__.py
# Register DropSend Setup + AutoUploader nodes
import os
import logging
import logging.handlers
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Attach a FileHandler to the root logger so every child logger in this
# plugin (`logging.getLogger(__name__)` in our modules) gets its records
# persisted to dropsend.log alongside ComfyUI's own stdout. We do NOT
# use logging.basicConfig() here: ComfyUI's main.py configures the root
# logger before our package is imported, and basicConfig is a no-op
# once any caller has already configured root.
#
# Race-free perms: pre-create the file with 0o600 via os.open() before
# FileHandler can create it under the default umask (typically 0o644).
# A follow-up chmod tightens perms if the file already existed with
# looser bits.
_LOG_PATH = os.path.join(os.path.dirname(__file__), "dropsend.log")
try:
    _fd = os.open(_LOG_PATH, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    os.close(_fd)
except OSError:
    pass
_root_logger = logging.getLogger()
if not any(
    isinstance(h, logging.FileHandler)
    and getattr(h, "baseFilename", "") == _LOG_PATH
    for h in _root_logger.handlers
):
    try:
        # Rotating handler caps disk use: 5 MB per file, 3 backups +
        # current = 4 files = ~20 MB max. On a busy host, plain
        # FileHandler grows unbounded over months; rotation prevents
        # a tiny background process from filling someone's home dir.
        _fh = logging.handlers.RotatingFileHandler(
            _LOG_PATH,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        _fh.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        )
        _root_logger.addHandler(_fh)
        # If ComfyUI didn't set a root level (or set it higher than INFO),
        # raise enough that our INFO records actually reach the handler.
        if _root_logger.level == logging.NOTSET or _root_logger.level > logging.INFO:
            _root_logger.setLevel(logging.INFO)
    except OSError:
        pass
try:
    os.chmod(_LOG_PATH, 0o600)
except OSError:
    pass

# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------
# Load .env from the plugin directory at import time so DROPBOX_APP_KEY,
# DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN, COMFYUI_ENCRYPTION_KEY, and
# the uploader's persisted settings are visible in os.environ before any
# node runs. override=False is intentional — host-injected env vars
# (RunPod secrets, Docker env, systemd EnvironmentFile) take precedence
# over the plugin's local .env.
_PLUGIN_ENV = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_PLUGIN_ENV):
    load_dotenv(_PLUGIN_ENV, override=False)

from .dropsend_uploader_node import NODE_CLASS_MAPPINGS as RUN_CLASS, NODE_DISPLAY_NAME_MAPPINGS as RUN_DISPLAY
from .dropsend_setup_node import NODE_CLASS_MAPPINGS as SETUP_CLASS, NODE_DISPLAY_NAME_MAPPINGS as SETUP_DISPLAY
NODE_CLASS_MAPPINGS = {}
NODE_CLASS_MAPPINGS.update(RUN_CLASS)
NODE_CLASS_MAPPINGS.update(SETUP_CLASS)
NODE_DISPLAY_NAME_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS.update(RUN_DISPLAY)
NODE_DISPLAY_NAME_MAPPINGS.update(SETUP_DISPLAY)
# Define web directory for JavaScript extensions
WEB_DIRECTORY = "./web"
