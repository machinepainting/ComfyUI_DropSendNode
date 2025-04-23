# ComfyUI_DropSendNode/monitor_output.py

import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .dropbox_upload import upload_to_dropbox

uploaded_files = set()

def start_monitoring(folder, dropbox_dest_folder):
    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            file_path = event.src_path

            # Wait for file to finish writing
            while True:
                try:
                    with open(file_path, 'rb') as f:
                        f.read()
                    break
                except Exception:
                    time.sleep(0.5)

            if file_path not in uploaded_files:
                try:
                    upload_to_dropbox(file_path, dropbox_dest_folder)
                    uploaded_files.add(file_path)
                    print(f"📦✅ Uploaded: {file_path}")
                except Exception as e:
                    print(f"📦❌ Upload failed: {e}")

    # Ensure the folder exists
    if not os.path.exists(folder):
        os.makedirs(folder)

    observer = Observer()
    observer.schedule(Handler(), folder, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
