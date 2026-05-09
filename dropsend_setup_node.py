# dropsend_setup_node.py

import os
import re
import time
import threading
import requests
import webbrowser
import uuid
import json
from dotenv import load_dotenv, dotenv_values
import urllib.parse
from .dropbox_auth_manager import DropboxAuthManager
from cryptography.fernet import Fernet


# ---------------------------------------------------------------------------
# Out-of-band secret transport
#
# ComfyUI persists every queued prompt's input JSON in
# PromptServer.history, which is exposed on the unauthenticated
# /history endpoint. If the Setup Node accepts app_key/app_secret/
# auth_code as workflow inputs, those values are visible there for the
# lifetime of history entry — a real exposure on any network-reachable
# pod (RunPod tunnel, public ComfyUI UI, etc.).
#
# To close it: the JS extension intercepts Queue, POSTs the secret
# widget values to /dropsend/setup/stash (this module's route), clears
# the widgets, then lets the queue go through. The prompt JSON ComfyUI
# stores in history therefore has empty strings for the secret fields.
# When this node's setup() actually runs, it pulls the real values
# from the stash (one-shot, keyed by the originating client_id).
#
# Entries auto-expire after _SETUP_STASH_TTL_SEC so a stash POST that's
# never consumed (user closed the tab between stash and queue, etc.)
# doesn't sit in memory.
# ---------------------------------------------------------------------------

_setup_secret_stash = {}
_setup_secret_lock = threading.Lock()
_SETUP_STASH_TTL_SEC = 60
_SETUP_STASH_MAX_ENTRIES = 32  # cap to bound memory under stash-spam abuse
_CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# Per-IP rate limit on the stash route. Defense-in-depth against an
# attacker on the same network firing thousands of stash POSTs to
# evict a legitimate user's entry between Save and Queue (the entry
# eviction policy is oldest-first to favour fresh writes, but a
# sufficiently fast attacker can still race).
_STASH_RL_WINDOW_SEC = 10
_STASH_RL_MAX_PER_WINDOW = 30
_stash_rl_state = {}
_stash_rl_lock = threading.Lock()


def _stash_rl_check(remote_ip):
    """Return True if `remote_ip` is under the per-window POST budget,
    False if it should be 429'd. Updates the bucket in place."""
    if not remote_ip:
        return True  # don't block requests we can't attribute
    now = time.time()
    cutoff = now - _STASH_RL_WINDOW_SEC
    with _stash_rl_lock:
        # Lazy GC: only walk the dict every ~50 hits, otherwise this
        # is O(N) per request and turns into its own DoS.
        if len(_stash_rl_state) > 256:
            stale = [ip for ip, hits in _stash_rl_state.items() if not hits or hits[-1] < cutoff]
            for ip in stale:
                _stash_rl_state.pop(ip, None)
        hits = _stash_rl_state.setdefault(remote_ip, [])
        # Drop hits outside the window.
        i = 0
        while i < len(hits) and hits[i] < cutoff:
            i += 1
        if i:
            del hits[:i]
        if len(hits) >= _STASH_RL_MAX_PER_WINDOW:
            return False
        hits.append(now)
        return True


def _stash_prune_expired_locked():
    now = time.time()
    expired = [k for k, (ts, _v) in _setup_secret_stash.items() if now - ts > _SETUP_STASH_TTL_SEC]
    for k in expired:
        _setup_secret_stash.pop(k, None)


def _stash_set(client_id, payload):
    with _setup_secret_lock:
        _stash_prune_expired_locked()
        if len(_setup_secret_stash) >= _SETUP_STASH_MAX_ENTRIES and client_id not in _setup_secret_stash:
            # Evict the oldest entry rather than refuse the write — the
            # legitimate user's most recent attempt should win over
            # whatever's been sitting around.
            oldest_key = min(_setup_secret_stash, key=lambda k: _setup_secret_stash[k][0])
            _setup_secret_stash.pop(oldest_key, None)
        _setup_secret_stash[client_id] = (time.time(), payload)


def _stash_consume(client_id):
    with _setup_secret_lock:
        _stash_prune_expired_locked()
        entry = _setup_secret_stash.pop(client_id, None)
    if entry is None:
        return None
    _ts, payload = entry
    return payload


def _register_stash_route_once():
    """Register the /dropsend/setup/stash POST handler on PromptServer.

    Idempotent — repeat calls are no-ops. Called at module import; if
    PromptServer isn't ready yet, registration is silently skipped (the
    Setup Node falls back to reading secrets from prompt inputs, the
    legacy/insecure path).
    """
    if getattr(_register_stash_route_once, "_registered", False):
        return
    try:
        from server import PromptServer
        from aiohttp import web
    except Exception:
        return
    instance = getattr(PromptServer, "instance", None)
    if instance is None or not hasattr(instance, "routes"):
        return

    @instance.routes.post("/dropsend/setup/stash")
    async def _stash_handler(request):
        # Same-origin enforcement. The browser sends an Origin header on
        # POSTs; we require it to match the host the request was made to.
        # Without this, a malicious page in another tab could attempt a
        # CSRF POST against http://127.0.0.1:8188 — and while the live-
        # WebSocket-session check would block injection without a known
        # client_id, an attacker who sniffed the WS could still try.
        # Origin check closes the cross-origin path entirely.
        origin = request.headers.get("Origin", "")
        if origin:
            try:
                from urllib.parse import urlparse
                origin_host = urlparse(origin).netloc
            except Exception:
                origin_host = ""
            if not origin_host or origin_host != request.host:
                return web.json_response({"error": "cross-origin denied"}, status=403)

        # Content-Type lockdown: only accept JSON. Closes the confused-
        # deputy class where a form-encoded body is parsed as JSON.
        if request.content_type and request.content_type != "application/json":
            return web.json_response(
                {"error": "Content-Type must be application/json"},
                status=415,
            )

        # Per-IP rate limit. Defense-in-depth against stash-spam DoS
        # attempting to evict a legitimate user's entry by overflowing
        # the entry cap.
        remote_ip = request.headers.get("X-Forwarded-For", request.remote or "").split(",")[0].strip()
        if not _stash_rl_check(remote_ip):
            return web.json_response({"error": "rate limit"}, status=429)

        # Reject oversized bodies before json-decoding to avoid a
        # malicious large-payload memory spike.
        if request.content_length is not None and request.content_length > 32 * 1024:
            return web.json_response({"error": "payload too large"}, status=413)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)
        client_id = data.get("client_id") if isinstance(data, dict) else None
        if not client_id or not isinstance(client_id, str) or not _CLIENT_ID_PATTERN.match(client_id):
            return web.json_response({"error": "client_id required"}, status=400)

        # Authenticate by liveness: only accept stash writes for a
        # client_id that currently has an active WebSocket connection
        # to this PromptServer instance. Closes the "attacker on the
        # same network injects credentials by guessing a victim's
        # client_id" vector — the attacker would need both the
        # client_id AND a live WS bound to it under that ID.
        try:
            sockets = getattr(instance, "sockets", None)
            if not sockets or client_id not in sockets:
                return web.json_response({"error": "client_id has no active WebSocket"}, status=403)
        except Exception:
            return web.json_response({"error": "internal"}, status=500)

        payload = {
            "app_key": str(data.get("app_key") or ""),
            "app_secret": str(data.get("app_secret") or ""),
            "auth_code": str(data.get("auth_code") or ""),
        }
        # Drop entries that have nothing to stash, saves memory and
        # avoids weird empty-stash-overrides-real-input behaviour.
        if not any(payload.values()):
            return web.json_response({"ok": True, "stashed": False})
        _stash_set(client_id, payload)
        return web.json_response({"ok": True, "stashed": True})

    _register_stash_route_once._registered = True
    print("[DropSend Setup] Registered /dropsend/setup/stash route (out-of-band secret transport)")


_register_stash_route_once()


# Workflow inputs to the setup node can come from any caller that can submit
# a workflow to ComfyUI. On a network-reachable host that means a remote
# attacker can (a) wipe credentials via reconnect=True or (b) overwrite the
# stored Dropbox app to redirect uploads to their own account. We therefore
# require the operator to opt in by setting this env var on the host before
# the setup node will perform any state-changing action.
_SETUP_OPT_IN_VAR = "COMFYUI_DROPSEND_ALLOW_SETUP"
_SETUP_OPT_IN_HELP = (
    f"Setup is disabled. To allow this node to write or clear credentials, "
    f"set {_SETUP_OPT_IN_VAR}=1 in the host environment before starting "
    f"ComfyUI, or provision DROPBOX_APP_KEY / DROPBOX_APP_SECRET / "
    f"DROPBOX_REFRESH_TOKEN directly via environment variables (e.g. RunPod "
    f"secrets). This guard prevents remote workflow submitters from "
    f"hijacking or wiping your Dropbox connection."
)


def _setup_opt_in_enabled():
    return os.getenv(_SETUP_OPT_IN_VAR, "").strip().lower() in ("1", "true", "yes")


# Names of fields treated as secrets when redacting the console banner.
# Every field the Setup Node emits is a credential, so all four are
# redacted. The destination folder is owned by the AutoUploader and
# never passes through this node.
_SECRET_FIELDS = {
    "DROPBOX_APP_KEY",
    "DROPBOX_APP_SECRET",
    "DROPBOX_REFRESH_TOKEN",
    "COMFYUI_ENCRYPTION_KEY",
}


def _redact(value, visible_tail=4):
    """Return value with all but the last few characters masked."""
    if not value:
        return ""
    if len(value) <= visible_tail:
        return "*" * len(value)
    return "*" * (len(value) - visible_tail) + value[-visible_tail:]


def _redact_kv_line(line):
    """Redact a 'NAME=value' line if NAME is in _SECRET_FIELDS."""
    name, sep, value = line.partition("=")
    if sep and name in _SECRET_FIELDS:
        return f"{name}={_redact(value)}"
    return line

class DropSendSetupNode:
    @classmethod
    def INPUT_TYPES(cls):
        # Architecture: this node has NO credential-bearing inputs.
        # app_key, app_secret, and auth_code never enter the workflow
        # prompt JSON, never reach PromptServer.history, never get
        # serialized into PNG metadata or saved workflows. They are
        # entered by the user in a browser-only modal launched from
        # the JS extension's "Set credentials…" button, POSTed
        # directly to the same-origin route /dropsend/setup/stash, and
        # consumed once on the next Queue from the in-process stash
        # keyed by client_id. The only inputs on the node are
        # configuration knobs that aren't sensitive.
        return {
            "required": {
                "storage_method": (["env_file", "display_only"], {
                    "label": "Credential Storage Method",
                    "default": "display_only"
                }),
                "encryption_key_method": (["off", "Display Only", "save to .env"], {
                    "label": "Encryption Key Method",
                    "default": "Display Only"
                }),
            },
            "optional": {
                "reconnect": ("BOOLEAN", {
                    "label": "Reset stored credentials",
                    "default": False
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_NODE = True
    FUNCTION = "setup"

    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        # Force re-execution on every Queue. Setup is intentionally
        # side-effecting (writes/clears .env, exchanges auth codes,
        # refreshes tokens) and the input dict here doesn't reflect
        # the actual work — the real driver is the out-of-band stash
        # entry, which ComfyUI's input-hash cache cannot see. Always
        # returning NaN means setup() runs every time the user clicks
        # Queue, which is the correct semantics for this node.
        return float("NaN")

    def setup(self, storage_method="display_only", encryption_key_method="Display Only", reconnect=False):
        try:
            print(f"[DropSend Setup] Called: reconnect={reconnect}, storage_method={storage_method}, encryption_key_method={encryption_key_method}")

            # Credentials live exclusively in the per-session out-of-band
            # stash keyed by client_id, populated by the browser modal
            # via POST /dropsend/setup/stash. There are no fallback
            # paths — if the stash is empty for this client, the user
            # has to click "Set credentials…" on the node and enter
            # values there. This is the architectural guarantee that
            # /history, PNG metadata, workflow JSON, and localStorage
            # never see the secret fields.
            app_key = None
            app_secret = None
            auth_code = None
            try:
                from server import PromptServer
                sid = getattr(PromptServer.instance, "client_id", None)
                if sid:
                    stashed = _stash_consume(sid)
                    if stashed:
                        app_key = stashed.get("app_key") or None
                        app_secret = stashed.get("app_secret") or None
                        auth_code = stashed.get("auth_code") or None
                        print("[DropSend Setup] Loaded secrets from out-of-band stash")
            except Exception as e:
                print(f"[DropSend Setup] Warning: could not consume secret stash: {e}")

            print(f"[DropSend Setup] Inputs present: app_key={bool(app_key)}, app_secret={bool(app_secret)}, auth_code={bool(auth_code)}")

            # Initialize auth manager
            auth_manager = DropboxAuthManager()
            print(f"[DropSend Setup] Auth manager initialized")
            
            # Handle reconnect/reset request
            if reconnect:
                if not _setup_opt_in_enabled():
                    message = (
                        "Reconnect refused: " + _SETUP_OPT_IN_HELP
                    )
                    print(f"[DropSend Setup] {message}")
                    return {"ui": {"text": [message]}, "result": (message,)}

                print("[DropSend Setup] Reconnect requested - clearing all credentials")

                # Populate the auth manager from os.environ (which
                # was loaded from .env at module import) so the reset
                # call has the credentials needed to revoke the
                # refresh token at Dropbox. Without this, a leaked
                # refresh_token + app_secret pair would still be valid
                # at Dropbox until manually revoked. Revocation is
                # best-effort with an 8-second timeout (see
                # DropboxAuthManager.reset) — local cleanup proceeds
                # regardless.
                auth_manager.app_key = os.environ.get("DROPBOX_APP_KEY") or auth_manager.app_key
                auth_manager.app_secret = os.environ.get("DROPBOX_APP_SECRET") or auth_manager.app_secret
                auth_manager.refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN") or auth_manager.refresh_token

                print("[DropSend Setup] Clearing all stored credentials")
                auth_manager.reset(revoke_token=True)

                # Manually clear all credential files
                node_dir = os.path.dirname(__file__)

                # Clear .env file if it exists
                env_path = os.path.join(node_dir, ".env")
                if os.path.exists(env_path):
                    print(f"[DropSend Setup] Removing .env file: {env_path}")
                    os.remove(env_path)

                # Clear in-process os.environ for the credential keys.
                # __init__.py's load_dotenv() copies .env values into
                # os.environ at module import; deleting .env on disk
                # does not unset those copies. Without this, the next
                # Setup run hits the `env_vars_set` short-circuit at
                # line ~165 and returns "credentials found in system
                # environment variables" — even though the user is
                # mid-reconfigure and expects to enter a new auth code.
                # We don't touch DROPBOX_FOLDER (a path, not a credential)
                # or COMFYUI_ENCRYPTION_KEY (kept across reconnects).
                for key in ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN", "DROPBOX_ACCESS_TOKEN"):
                    if key in os.environ:
                        os.environ.pop(key, None)
                        print(f"[DropSend Setup] Cleared {key} from process environment")
                
                # Send WebSocket notification to the originating browser
                # so its auth fields refresh. Refuse to broadcast — if
                # there's no client_id (e.g. CLI submission without one
                # in the prompt JSON), every connected browser tab on
                # this ComfyUI instance would otherwise refresh.
                try:
                    from server import PromptServer
                    sid = getattr(PromptServer.instance, "client_id", None)
                    if not sid:
                        print(
                            "[DropSend Setup] Skipping reconnect-complete "
                            "broadcast: prompt has no client_id (CLI "
                            "submission?). Submit from the ComfyUI web UI "
                            "to receive the refresh notification."
                        )
                    else:
                        message_data = {
                            "type": "dropbox_reconnect_complete",
                            "success": True,
                            "client_id": sid,
                            "message": "Credentials cleared - ComfyUI will refresh to show auth fields",
                        }
                        PromptServer.instance.send_sync(
                            "dropbox_reconnect_complete", message_data, sid
                        )
                        print(f"[DropSend Setup] Sent WebSocket notification for reconnect completion")
                except Exception as e:
                    print(f"[DropSend Setup] Warning: Could not send WebSocket notification: {e}")
                
                message = "Dropbox credentials cleared. ComfyUI will refresh to show auth fields..."
                print(f"[DropSend Setup] {message}")
                return {
                    "ui": {"text": [message]},
                    "result": (message,)
                }
            
            # Check for environment variables (from any source)
            env_vars_set = all([
                os.getenv("DROPBOX_APP_KEY"),
                os.getenv("DROPBOX_APP_SECRET"), 
                os.getenv("DROPBOX_REFRESH_TOKEN")
            ])
            if env_vars_set:
                message = "Dropbox credentials found in system environment variables. Ready to upload files."
                print(f"[DropSend Setup] {message}")
                return {
                    "ui": {"text": [message]},
                    "result": (message,)
                }

            # Check for RunPod secrets
            runpod_env_set = all([
                os.getenv("RUNPOD_SECRET_DROPBOX_ACCESS_TOKEN"),
                os.getenv("RUNPOD_SECRET_DROPBOX_REFRESH_TOKEN")
            ])
            if runpod_env_set:
                return ("Warning: Detected RunPod secrets. Using those instead.",)

            # New setup flow using DropboxAuthManager.
            #
            # Below this point the node accepts Dropbox app credentials from
            # workflow inputs and persists them. On a remotely-reachable
            # ComfyUI instance that flow is exploitable — a workflow author
            # could swap in their own Dropbox app to redirect uploads. Gate
            # it behind an explicit operator opt-in.
            if not _setup_opt_in_enabled():
                message = _SETUP_OPT_IN_HELP
                print(f"[DropSend Setup] {message}")
                return {"ui": {"text": [message]}, "result": (message,)}

            print(f"[DropSend Setup] Starting new setup flow")

            # Clean up the inputs first
            app_key_clean = app_key.strip() if app_key else ""
            app_secret_clean = app_secret.strip() if app_secret else ""
            auth_code_clean = auth_code.strip() if auth_code else ""
            
            # Log only the lengths, not the values themselves.
            print(f"[DropSend Setup] Cleaned input lengths: app_key={len(app_key_clean)}, app_secret={len(app_secret_clean)}, auth_code={len(auth_code_clean)}")
            
            # Check if we have app credentials
            if not app_key_clean or not app_secret_clean:
                message = "Error: Missing App Key or App Secret. Please provide both."
                print(f"[DropSend Setup] {message}")
                return (message,)
            
            # If no auth code, generate OAuth URL for manual code flow
            if not auth_code_clean:
                print(f"[DropSend Setup] No auth code provided - generating OAuth URL for manual flow")
                auth_temp = DropboxAuthManager(app_key=app_key_clean)

                # Manual OAuth flow without redirect_uri (Dropbox will display the code)
                oauth_url = auth_temp.get_oauth_url(force_reapprove=True)

                # Print a high-visibility banner with the OAuth URL so the
                # operator can see it directly in the ComfyUI terminal
                # without needing to wire a Show Text node to the Setup
                # Node's output. The URL contains only the OAuth client_id
                # (Dropbox app_key) — semi-public per Dropbox's design,
                # not a credential — so it's safe to print to console.
                print()
                print("=" * 80)
                print("DROPSEND — DROPBOX AUTHORIZATION REQUIRED")
                print("=" * 80)
                print("Open this URL in your browser to authorize:")
                print()
                print(f"  {oauth_url}")
                print()
                print("After authorizing, Dropbox will display an authorization code.")
                print("Paste it into the credentials modal that auto-opened in your")
                print("browser, then click Save and re-queue this workflow.")
                print("=" * 80)
                print()

                # Auto-open the credentials-entry modal in the originating
                # browser so the user can paste the auth_code as soon as
                # Dropbox shows it. Same client_id-only delivery pattern
                # we use for the credentials_ready event — refuse if
                # there's no client_id (CLI submission), otherwise the
                # event would broadcast to every connected browser tab.
                try:
                    from server import PromptServer
                    sid = getattr(PromptServer.instance, "client_id", None)
                    if sid:
                        PromptServer.instance.send_sync(
                            "dropsend_credentials_needed",
                            {"client_id": sid, "stage": "auth_code"},
                            sid,
                        )
                        print("[DropSend Setup] Sent credentials-needed event to browser (auto-opens modal for auth_code paste)")
                except Exception as e:
                    print(f"[DropSend Setup] Warning: could not send credentials-needed event: {e}")

                message = (
                    f"Dropbox OAuth Ready!\n\n"
                    f"Click the link below to authorize with Dropbox "
                    f"(also printed in the ComfyUI terminal):\n\n"
                    f"{oauth_url}\n\n"
                    f"A popup window will open. After authorization, Dropbox "
                    f"will show your auth code.\nCopy the code and paste it "
                    f"into the 'auth_code' field above, then run this node again."
                )

                # Use ComfyUI's dynamic return format for better UI integration
                return {
                    "ui": {"text": [message]},
                    "result": (message,)
                }

            # Exchange auth code for refresh token using DropboxAuthManager
            print(f"[DropSend Setup] Attempting to exchange auth code")
            auth_manager_setup = DropboxAuthManager(app_key_clean, app_secret_clean)
            
            # Get the tokens without storing them yet
            # Use manual OAuth flow (auth codes from manual copy/paste)
            print(f"[DropSend Setup] Using manual OAuth flow")
            result = auth_manager_setup.exchange_auth_code_raw(auth_code_clean)
            refresh_token = result.get("refresh_token")
            
            print(f"[DropSend Setup] Auth code exchange successful")
            print(f"[DropSend Setup] Using storage method: {storage_method}")
            
            # Generate encryption key only if encryption_key_method is not "off"
            encryption_key = None
            if encryption_key_method != "off":
                encryption_key = Fernet.generate_key().decode()

            # Route each credential to one of two destinations based on the
            # user's two independent choices:
            #
            #   storage_method       = env_file      | display_only
            #   encryption_key_method= save to .env  | Display Only | off
            #
            # `env_file` / `save to .env`  -> persist to .env on disk
            # `display_only` / `Display Only` -> deliver to the originating
            #     browser via a WebSocket side-channel that does NOT pass
            #     through the node's `ui` or `result`. Both of those land in
            #     PromptServer.history (see ComfyUI execution.py — the
            #     history_result["outputs"] dict is built from ui_outputs),
            #     which is served on the unauthenticated /history endpoint
            #     and would expose any credential placed there. Cloud users
            #     (RunPod, Docker) explicitly choose `display_only` to keep
            #     credentials out of the pod's filesystem entirely.
            env_writes = []   # (NAME, value) pairs to persist to .env
            ws_payload = {}   # NAME -> value, delivered via WebSocket only

            dropbox_creds = [
                ("DROPBOX_APP_KEY", app_key_clean),
                ("DROPBOX_APP_SECRET", app_secret_clean),
                ("DROPBOX_REFRESH_TOKEN", refresh_token),
            ]
            if storage_method == "env_file":
                env_writes.extend(dropbox_creds)
            else:
                for name, value in dropbox_creds:
                    ws_payload[name] = value

            if encryption_key_method == "save to .env" and encryption_key:
                env_writes.append(("COMFYUI_ENCRYPTION_KEY", encryption_key))
            elif encryption_key_method == "Display Only" and encryption_key:
                ws_payload["COMFYUI_ENCRYPTION_KEY"] = encryption_key

            # Merge with any existing .env so re-running setup is non-destructive.
            #
            # - Non-setup keys (e.g. the AutoUploader's ENABLE_ENCRYPTION,
            #   POST_DELETE_ENC, etc.) survive a setup re-run unchanged.
            # - Setup keys whose destination this run is NOT the .env file
            #   are dropped from disk: either they're being rewritten from
            #   env_writes, or they're being delivered via the browser-only
            #   WebSocket and the old on-disk copy is now stale. Switching
            #   from env_file -> display_only therefore actually scrubs the
            #   credential lines off disk, instead of leaving stale secrets
            #   in .env.
            # - The race-free open (O_CREAT with mode 0o600) keeps the file
            #   from being world/group-readable in the open->chmod window.
            # Keys the Setup Node "owns" — these get scrubbed from .env
            # on a setup re-run that's not writing them back, so old
            # values don't linger when switching env_file -> display_only.
            # DROPBOX_FOLDER is intentionally absent: it's owned by the
            # AutoUploader, not Setup, and would otherwise get wiped
            # whenever the user re-runs Setup to rotate credentials.
            SETUP_KEYS = {
                "DROPBOX_APP_KEY",
                "DROPBOX_APP_SECRET",
                "DROPBOX_REFRESH_TOKEN",
                "COMFYUI_ENCRYPTION_KEY",
            }

            node_dir = os.path.dirname(__file__)
            env_path = os.path.join(node_dir, ".env")

            existing = {}
            if os.path.exists(env_path):
                existing = dict(dotenv_values(env_path))

            preserved = {k: v for k, v in existing.items() if k not in SETUP_KEYS}
            merged = dict(preserved)
            for name, value in env_writes:
                merged[name] = value

            if merged:
                fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as f:
                    for k, v in merged.items():
                        f.write(f"{k}={v}\n")
                if env_writes:
                    # Load the freshly-written values into os.environ so
                    # they are usable by the AutoUploader (or any other
                    # node) in the same ComfyUI session, without requiring
                    # a restart.
                    load_dotenv(env_path, override=True)
                # If env_writes is empty (e.g. display_only re-run that
                # only scrubbed credentials), don't load — the new file
                # has no credentials we'd want to push into os.environ.
            elif os.path.exists(env_path):
                # No setup keys this run AND nothing else worth keeping —
                # remove the empty-shell file rather than leave a 0-byte
                # 0600 file behind.
                os.remove(env_path)

            # Deliver the browser-only payload via PromptServer's WebSocket
            # to the originating client. This data is NOT included in the
            # node's `ui` or `result` and is therefore never persisted in
            # PromptServer.history.
            #
            # Security: refuse to send if the prompt has no client_id.
            # ComfyUI's send_sync with sid=None broadcasts to *every*
            # connected WebSocket client (server.py send_json: when sid
            # is None it iterates self.sockets). On a network-reachable
            # host (RunPod tunnel, LAN, etc.) that means a CLI/curl/SDK
            # submission without a client_id field would push the
            # credentials to any browser tab pointed at the same ComfyUI
            # instance. So we treat "no client_id" as a delivery failure
            # and surface it to the operator instead.
            ws_delivered = False
            ws_delivery_error = None
            if ws_payload:
                try:
                    from server import PromptServer
                    sid = getattr(PromptServer.instance, "client_id", None)
                    if not sid:
                        ws_delivery_error = (
                            "prompt has no client_id (typical for CLI/curl/SDK "
                            "submissions). display_only delivery requires "
                            "submitting from the ComfyUI web browser so a "
                            "client_id is attached to the prompt."
                        )
                        msg = (
                            "[DropSend Setup] Refusing to deliver credentials: "
                            "prompt has no client_id. Sending to sid=None would "
                            "broadcast to every connected browser. Submit from "
                            "the ComfyUI web UI instead."
                        )
                        print(msg)
                        try:
                            import logging as _logging
                            _logging.getLogger(__name__).warning(msg)
                        except Exception:
                            pass
                    else:
                        # Echo the sid inside the payload so the JS handler
                        # can defense-in-depth verify it matches api.clientId
                        # and ignore mismatched events.
                        PromptServer.instance.send_sync(
                            "dropsend_credentials_ready",
                            {"credentials": dict(ws_payload), "client_id": sid},
                            sid,
                        )
                        ws_delivered = True
                except Exception as e:
                    ws_delivery_error = str(e)
                    print(f"[DropSend Setup] WebSocket delivery failed: {e}")

            # Build the result/ui message — contains NO credential values.
            # Both `ui` and `result` are persisted in PromptServer.history.
            # Keep it short and action-oriented: tell the user the one
            # thing to do next.
            message_parts = ["Dropbox connected."]
            if ws_payload and ws_delivered:
                # display_only path (covers the mixed case where env_writes
                # also happened — the panel still has values the user must
                # manually copy into platform secrets before they're useful).
                # Two-step framing: most cloud platforms (RunPod, Docker,
                # K8s) require a container/pod restart for newly-added
                # secrets to take effect. So "copy then run" is wrong;
                # the correct flow is "copy, then configure secrets, then
                # restart the pod, then on the new pod remove the Setup
                # node and run AutoUploader".
                message_parts.append(
                    "Next steps:\n"
                    "  1. Copy each value from the DropSend Credentials "
                    "panel to a safe place (password manager, secure note).\n"
                    "  2. Add them to your platform's secrets configuration "
                    "(RunPod Secrets, Docker env, systemd EnvironmentFile).\n"
                    "  3. Restart your pod / container so the new secrets "
                    "are visible to the ComfyUI process.\n"
                    "  4. On the restarted pod, remove this Setup node "
                    "from your workflow and run the 'DropSend - AutoUploader' "
                    "node."
                )
            elif ws_payload and not ws_delivered:
                # Failure-mode message. The two audiences and what each
                # should do:
                #   • Cloud users (RunPod, hosted) using display_only —
                #     must submit from the web UI so a client_id is on
                #     the prompt. They should NOT switch to env_file
                #     because that puts secrets on the pod's filesystem,
                #     which is exactly what display_only is designed to
                #     avoid.
                #   • Local users — env_file is a reasonable fallback.
                message_parts.append(
                    f"Browser delivery refused: {ws_delivery_error}\n\n"
                    f"What to do:\n"
                    f"  • Cloud / RunPod / hosted ComfyUI:  Submit this "
                    f"workflow from your web browser (not via curl / API / "
                    f"SDK). The browser's WebSocket connection attaches a "
                    f"client_id automatically. display_only never writes "
                    f"credentials to the pod's filesystem.\n"
                    f"  • Local install only:  If you're running ComfyUI on "
                    f"the same machine you're using and don't mind "
                    f"credentials in a 0600 .env file on disk, switch "
                    f"storage_method to 'env_file' and rerun."
                )
            elif env_writes:
                # env_file path: creds are already loaded into the running
                # process; user just needs to remove the Setup node.
                message_parts.append(
                    "You can remove this Setup node from your workflow "
                    "and run the 'DropSend - AutoUploader' node."
                )
            elif existing and any(k in SETUP_KEYS for k in existing):
                # Re-run that scrubbed previously-written credential lines
                # from .env (typical when switching env_file -> display_only).
                message_parts.append(
                    "Previous credentials in .env were cleared because "
                    "this run delivers them another way."
                )

            message = "\n\n".join(message_parts)

            # Console banner — confirmation only, values redacted. The
            # operator who controls the host can verify what was set and
            # where, without secrets going to captured stdout.
            print("\n" + "=" * 80)
            print("DROPSEND SETUP COMPLETE (values redacted in console)")
            if env_writes:
                print(f"Wrote to file: {env_path}")
                for name, value in env_writes:
                    print("  " + _redact_kv_line(f"{name}={value}"))
            if ws_payload:
                label = "Sent to browser:" if ws_delivered else "FAILED to send to browser:"
                print(label)
                for name, value in ws_payload.items():
                    print("  " + _redact_kv_line(f"{name}={value}"))
            print("=" * 80 + "\n")

            print(f"[DropSend Setup] {message}")

            return {
                "ui": {"text": [message]},
                "result": (message,),
            }
            
        except Exception as e:
            message = f"Error: Setup failed: {e}"
            print(f"[DropSend Setup] ERROR: {message}")
            return {
                "ui": {"text": [message]},
                "result": (message,)
            }

# Required mappings for ComfyUI
NODE_CLASS_MAPPINGS = {"DropSendSetup": DropSendSetupNode}
NODE_DISPLAY_NAME_MAPPINGS = {"DropSendSetup": "📦⚙️ DropSend - Setup Node"}
