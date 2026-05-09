# ComfyUI_DropSendNode/monitor_output.py

import os
import time
import threading
import logging
from queue import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .dropbox_upload import upload_to_dropbox
from .encrypt_file import ENCRYPT_EXTENSIONS
from .safe_paths import is_safe_event_path

# Logging is configured by the package __init__ — see __init__.py for
# the FileHandler attached to the root logger. logging.getLogger here
# returns a child logger that propagates to root and inherits its
# handlers (file + ComfyUI's own stdout).
logger = logging.getLogger(__name__)

watcher_observer = None
watcher_handler = None
encryption_enabled = False
_stop_queue_processor = False  # Stop signal for queue processor

def wait_for_complete_write(file_path, timeout=10):
    last_size = -1
    stable_count = 0
    checks = 0

    while checks < timeout * 2:
        try:
            current_size = os.path.getsize(file_path)
            if current_size == last_size:
                stable_count += 1
                if stable_count >= 2:
                    return True
            else:
                stable_count = 0
                last_size = current_size
        except FileNotFoundError:
            pass
        time.sleep(0.5)
        checks += 1

    logger.warning(f"Timeout: File may still be writing: {file_path}")
    return False

def stop_queue_processor():
    """Signal the queue processor to stop."""
    global _stop_queue_processor
    _stop_queue_processor = True
    logger.info("Signaled upload queue processor to stop")

class NewFileHandler(FileSystemEventHandler):
    def __init__(self, dropbox_dest_folder, delete_enc=False):
        super().__init__()
        self.dropbox_dest_folder = dropbox_dest_folder
        self.delete_enc = delete_enc
        self.file_queue = Queue()
        self.start_queue_processor()

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = event.src_path
        # Defense-in-depth: refuse symlinks or paths whose realpath escapes
        # the allowed output roots. The watch_folder input is already
        # clamped, but Watchdog follows symlinks placed inside the watched
        # tree, so without this check a `output/leak.png -> ~/.ssh/id_rsa`
        # would still get uploaded.
        if not is_safe_event_path(file_path):
            logger.warning(f"Skipping unsafe path (symlink or outside output root): {file_path}")
            return
        if encryption_enabled and not file_path.lower().endswith('.enc'):
            logger.info(f"Skipping non-.enc file (encryption enabled): {file_path}")
            return
        if not encryption_enabled and file_path.lower().endswith('.enc'):
            logger.info(f"Skipping .enc file (encryption disabled): {file_path}")
            return
        logger.info(f"Detected new file: {file_path}")
        self.file_queue.put(file_path)

    def start_queue_processor(self):
        def process_queue():
            while not _stop_queue_processor:
                if not self.file_queue.empty():
                    file_path = self.file_queue.get()
                    if wait_for_complete_write(file_path):
                        try:
                            if upload_to_dropbox(file_path, self.dropbox_dest_folder):
                                if self.delete_enc and file_path.lower().endswith('.enc'):
                                    os.remove(file_path)
                                    logger.info(f"Deleted .enc file after upload: {file_path}")
                        except Exception as e:
                            logger.error(f"Upload failed: {e}")
                            self.file_queue.put(file_path)  # Requeue on failure
                time.sleep(0.1)  # Small delay to avoid CPU overload
            logger.info("Upload queue processor stopped")

        threading.Thread(target=process_queue, daemon=True).start()

def start_monitoring(watch_folder, dropbox_dest_folder, enable_encryption=False, delete_enc=False, subfolder_monitor=True, encrypt_handler=None):
    global watcher_observer, watcher_handler, encryption_enabled, _stop_queue_processor
    encryption_enabled = enable_encryption
    _stop_queue_processor = False  # Reset stop signal when starting

    if watcher_observer and watcher_observer.is_alive():
        logger.info("Restarting monitor to update settings.")
        watcher_observer.stop()
        watcher_observer.join()

    watcher_handler = NewFileHandler(dropbox_dest_folder, delete_enc)
    watcher_observer = Observer()
    watcher_observer.schedule(watcher_handler, watch_folder, recursive=subfolder_monitor)
    # macOS's _fsevents C extension maintains a global registry of watched
    # paths and refuses a second watch on the same path with a
    # "Cannot add watch ... it is already scheduled" RuntimeError that
    # crashes the second Observer's emitter thread silently. So when
    # encryption is enabled, register the encrypt handler on the SAME
    # Observer (watchdog supports multiple handlers per observer and
    # dispatches every event to every handler).
    if encrypt_handler is not None:
        watcher_observer.schedule(encrypt_handler, watch_folder, recursive=subfolder_monitor)
    watcher_observer.start()

    logger.info(f"📦👀 Watching: {watch_folder} (Subfolder_Monitor: {'Yes' if subfolder_monitor else 'No'})")
    logger.info(f"Upload target: {dropbox_dest_folder}")
    logger.info(f"Encryption enabled: {'Yes' if encryption_enabled else 'No'}")

    def keep_alive():
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            watcher_observer.stop()
        watcher_observer.join()

    threading.Thread(target=keep_alive, daemon=True).start()