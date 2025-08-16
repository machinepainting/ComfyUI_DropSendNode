# oauth_handler.py - OAuth callback handling for DropSendNode

import asyncio
from aiohttp import web
from .dropbox_auth_manager import DropboxAuthManager

# Global state to track pending OAuth flows
pending_oauth_sessions = {}

class OAuthCallbackHandler:
    def __init__(self):
        self.session_id = None
        self.app_key = None
        self.app_secret = None
        self.completion_callback = None
    
    def start_oauth_session(self, session_id, app_key, app_secret, completion_callback=None):
        """Start a new OAuth session and store the credentials for callback processing"""
        print(f"[OAuthHandler] Starting OAuth session: {session_id}")
        
        self.session_id = session_id
        self.app_key = app_key
        self.app_secret = app_secret
        self.completion_callback = completion_callback
        
        # Store in global pending sessions
        pending_oauth_sessions[session_id] = {
            'app_key': app_key,
            'app_secret': app_secret,
            'completion_callback': completion_callback,
            'handler': self
        }
        
        print(f"[OAuthHandler] OAuth session stored for: {session_id}")
    
    async def process_callback(self, auth_code, redirect_uri=None):
        """Process the OAuth callback with the received auth code"""
        try:
            print(f"[OAuthHandler] Processing callback for session: {self.session_id}")
            print(f"[OAuthHandler] Auth code received: {auth_code[:10]}...")
            print(f"[OAuthHandler] Redirect URI: {redirect_uri}")
            
            # Use DropboxAuthManager to exchange the code
            auth_manager = DropboxAuthManager(self.app_key, self.app_secret)
            auth_manager.exchange_auth_code(auth_code, redirect_uri=redirect_uri)
            
            print(f"[OAuthHandler] Auth code exchange successful")
            
            # Call completion callback if provided
            if self.completion_callback:
                await self.completion_callback(True, "✅ Dropbox connected successfully!")
            
            return True, "✅ Dropbox connected successfully! Credentials stored securely."
            
        except Exception as e:
            error_msg = f"❌ OAuth callback failed: {e}"
            print(f"[OAuthHandler] ERROR: {error_msg}")
            
            if self.completion_callback:
                await self.completion_callback(False, error_msg)
            
            return False, error_msg

# OAuth callback route handler
async def handle_oauth_callback(request):
    """Handle incoming OAuth callback from Dropbox"""
    try:
        # Extract parameters from callback
        auth_code = request.query.get('code')
        error = request.query.get('error')
        session_id = request.query.get('state')  # We'll use state parameter to track sessions
        
        print(f"[OAuthCallback] Received callback - code: {bool(auth_code)}, error: {error}, state: {session_id}")
        
        if error:
            error_msg = f"OAuth authorization failed: {error}"
            print(f"[OAuthCallback] ERROR: {error_msg}")
            return web.Response(text=f"""
            <html><body>
                <h2>❌ Authorization Failed</h2>
                <p>{error_msg}</p>
                <p>You can close this window and try again in ComfyUI.</p>
            </body></html>
            """, content_type='text/html', status=400)
        
        if not auth_code:
            print(f"[OAuthCallback] ERROR: No authorization code received")
            return web.Response(text="""
            <html><body>
                <h2>❌ No Authorization Code</h2>
                <p>No authorization code was received. Please try again.</p>
                <p>You can close this window and try again in ComfyUI.</p>
            </body></html>
            """, content_type='text/html', status=400)
        
        # Find the pending OAuth session
        if session_id and session_id in pending_oauth_sessions:
            session_data = pending_oauth_sessions[session_id]
            handler = session_data['handler']
            
            # Process the callback with the redirect URI
            callback_url = "http://localhost:8188/oauth/dropbox/callback"
            success, message = await handler.process_callback(auth_code, redirect_uri=callback_url)
            
            # Clean up the session
            del pending_oauth_sessions[session_id]
            
            if success:
                return web.Response(text=f"""
                <html><body>
                    <h2>✅ Authorization Successful!</h2>
                    <p>{message}</p>
                    <p>You can now close this window and return to ComfyUI.</p>
                    <script>
                        setTimeout(() => window.close(), 3000);
                    </script>
                </body></html>
                """, content_type='text/html')
            else:
                return web.Response(text=f"""
                <html><body>
                    <h2>❌ Setup Failed</h2>
                    <p>{message}</p>
                    <p>You can close this window and try again in ComfyUI.</p>
                </body></html>
                """, content_type='text/html', status=500)
        
        else:
            # Fallback for sessions without state tracking
            print("[OAuthCallback] No session found, attempting generic processing")
            return web.Response(text=f"""
            <html><body>
                <h2>🔄 Authorization Code Received</h2>
                <p>Please return to ComfyUI and manually enter this code:</p>
                <p><strong>{auth_code}</strong></p>
                <p>You can close this window after copying the code.</p>
            </body></html>
            """, content_type='text/html')
            
    except Exception as e:
        print(f"[OAuthCallback] Unexpected error: {e}")
        return web.Response(text=f"""
        <html><body>
            <h2>❌ Callback Error</h2>
            <p>An unexpected error occurred: {e}</p>
            <p>You can close this window and try again in ComfyUI.</p>
        </body></html>
        """, content_type='text/html', status=500)