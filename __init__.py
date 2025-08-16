# ComfyUI_DropSendNode/__init__.py
# Register Dropbox Setup + Run-only nodes

from .run_dropbox_node import NODE_CLASS_MAPPINGS as RUN_CLASS, NODE_DISPLAY_NAME_MAPPINGS as RUN_DISPLAY
from .setup_dropbox_node import NODE_CLASS_MAPPINGS as SETUP_CLASS, NODE_DISPLAY_NAME_MAPPINGS as SETUP_DISPLAY

NODE_CLASS_MAPPINGS = {}
NODE_CLASS_MAPPINGS.update(RUN_CLASS)
NODE_CLASS_MAPPINGS.update(SETUP_CLASS)

NODE_DISPLAY_NAME_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS.update(RUN_DISPLAY)
NODE_DISPLAY_NAME_MAPPINGS.update(SETUP_DISPLAY)

# Register OAuth callback route with ComfyUI server
def register_oauth_routes():
    """Register OAuth callback routes with ComfyUI's PromptServer"""
    try:
        from server import PromptServer
        from .oauth_handler import handle_oauth_callback
        
        # Add the OAuth callback route
        PromptServer.instance.app.router.add_get('/oauth/dropbox/callback', handle_oauth_callback)
        print("[DropSendNode] Registered OAuth callback route: /oauth/dropbox/callback")
        
    except Exception as e:
        print(f"[DropSendNode] Warning: Could not register OAuth routes: {e}")

# Register routes when the node is loaded
register_oauth_routes()
