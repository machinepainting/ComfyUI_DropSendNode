# ComfyUI_DropSendNode/monitor_output.py

import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .dropbox_upload import upload_to_dropbox

# Global reference to track and restart the monitor
watcher_observer = None
watcher_handler = None


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

    print(f"⚠️ Timeout: File may still be writing: {file_path}")
    return False


class NewFileHandler(FileSystemEventHandler):
    def __init__(self, dropbox_dest_folder):
        super().__init__()
        self.dropbox_dest_folder = dropbox_dest_folder

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = event.src_path
        print(f"📦✅ Detected new file: {file_path}")

        if not wait_for_complete_write(file_path):
            print(f"⚠️ Skipping upload: File not stable yet: {file_path}")
            return

        try:
            upload_to_dropbox(file_path, self.dropbox_dest_folder)
        except Exception as e:
            print(f"📦❌ Upload failed: {e}")


def start_monitoring(watch_folder, dropbox_dest_folder):
    global watcher_observer, watcher_handler

    # Stop and restart watcher if already running
    if watcher_observer and watcher_observer.is_alive():
        print("🔁 Restarting monitor to update destination folder.")
        watcher_observer.stop()
        watcher_observer.join()

    watcher_handler = NewFileHandler(dropbox_dest_folder)
    watcher_observer = Observer()
    watcher_observer.schedule(watcher_handler, watch_folder, recursive=False)
    watcher_observer.start()

    print(f"🔎🗂️ Now watching: {watch_folder}")
    print(f"📦📥 Upload target: {dropbox_dest_folder}")

    def keep_alive():
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            watcher_observer.stop()
        watcher_observer.join()

    threading.Thread(target=keep_alive, daemon=True).start()
