# safe_paths.py
#
# Path validation helpers used by DropSend nodes to constrain user-supplied
# paths to safe locations.
#
# Threat model: a ComfyUI instance may be reachable over the network. Any
# workflow author can therefore set node inputs. Without restriction, the
# DropSend uploader's watch_folder input becomes an arbitrary-file-read
# primitive — the watcher recursively uploads everything under the path to
# the operator's Dropbox account. We constrain watch_folder to the ComfyUI
# output directory tree, with an operator-controlled allowlist for advanced
# setups.

import os
import logging

logger = logging.getLogger(__name__)


def get_output_root():
    """Return the absolute, real path of ComfyUI's output directory.

    Falls back to <cwd>/output if folder_paths is unavailable (e.g. running
    unit tests outside a ComfyUI process).
    """
    try:
        import folder_paths  # type: ignore
        root = folder_paths.get_output_directory()
    except Exception:
        root = os.path.join(os.getcwd(), "output")
    return os.path.realpath(root)


def get_allowed_roots():
    """Return the list of directory roots a watch_folder is allowed to be in.

    Always includes the ComfyUI output directory. Operators who need to
    monitor additional locations (e.g. a custom output mount) can opt in by
    setting COMFYUI_DROPSEND_ALLOWED_WATCH_PATHS to an os.pathsep-separated
    list of absolute paths. Workflow inputs cannot expand this list.
    """
    roots = [get_output_root()]
    extra = os.environ.get("COMFYUI_DROPSEND_ALLOWED_WATCH_PATHS", "")
    if extra:
        for raw in extra.split(os.pathsep):
            raw = raw.strip()
            if raw:
                roots.append(os.path.realpath(raw))
    return roots


def _is_within(child, parent):
    """True iff `child` is `parent` or a descendant of it (after realpath)."""
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        # Different drives on Windows, etc.
        return False


def resolve_safe_watch_folder(user_input):
    """Resolve a user-supplied watch_folder to a safe absolute path.

    - Empty input → the ComfyUI output directory.
    - Relative input → joined under the output directory.
    - Absolute input → must resolve under one of the allowed roots.

    Raises ValueError with a clear message if the input escapes the allowed
    set (path traversal, symlinks pointing outside, unrelated absolute path).
    """
    output_root = get_output_root()
    allowed_roots = get_allowed_roots()

    if user_input is None or str(user_input).strip() == "":
        return output_root

    candidate = str(user_input).strip()

    if not os.path.isabs(candidate):
        candidate = os.path.join(output_root, candidate)

    resolved = os.path.realpath(candidate)

    for root in allowed_roots:
        if _is_within(resolved, root):
            return resolved

    raise ValueError(
        "watch_folder must be inside the ComfyUI output directory "
        f"({output_root}). Got: {user_input!r} (resolved: {resolved}). "
        "If you need to monitor a different location, set the "
        "COMFYUI_DROPSEND_ALLOWED_WATCH_PATHS environment variable on the "
        "host before starting ComfyUI."
    )


def is_safe_event_path(path):
    """True iff a Watchdog file event path is safe to process.

    Rejects (a) symlinks and (b) paths whose realpath escapes the allowed
    roots. Defends against symlinks placed inside the watched directory
    that point at sensitive files outside it (e.g. an output/leak.png
    -> ~/.ssh/id_rsa would otherwise be read, encrypted, and uploaded by
    the watchers).
    """
    try:
        if os.path.islink(path):
            return False
        resolved = os.path.realpath(path)
    except OSError:
        return False

    for root in get_allowed_roots():
        if _is_within(resolved, root):
            return True
    return False


def validate_dropbox_dest(dest):
    """Validate a Dropbox destination folder string.

    Dropbox paths are POSIX-style absolute paths. We reject empty values,
    paths missing the leading slash, parent-traversal segments, and NUL
    bytes. This is defense-in-depth — Dropbox itself does not interpret
    `..` — but it keeps malformed inputs from being silently accepted.
    """
    if dest is None or str(dest).strip() == "":
        raise ValueError("dropbox_dest_folder must not be empty.")

    value = str(dest).strip()

    if "\x00" in value:
        raise ValueError("dropbox_dest_folder contains a NUL byte.")
    if not value.startswith("/"):
        raise ValueError(
            f"dropbox_dest_folder must start with '/'. Got: {value!r}"
        )
    parts = [p for p in value.split("/") if p]
    if any(p == ".." for p in parts):
        raise ValueError(
            f"dropbox_dest_folder must not contain '..' segments. Got: {value!r}"
        )

    return "/" + "/".join(parts) if parts else "/"
