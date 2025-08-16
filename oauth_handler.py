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
            
            # Send WebSocket message to trigger ComfyUI refresh
            try:
                from server import PromptServer
                message_data = {
                    "type": "dropbox_oauth_complete",
                    "session_id": self.session_id,
                    "success": True,
                    "message": "✅ Dropbox connected successfully!"
                }
                PromptServer.instance.send_sync("dropbox_oauth_complete", message_data)
                print(f"[OAuthHandler] Sent WebSocket notification for OAuth completion")
            except Exception as e:
                print(f"[OAuthHandler] Warning: Could not send WebSocket notification: {e}")
            
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
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Dropbox Authorization Successful</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            margin: 0;
                            padding: 40px 20px;
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                        }}
                        .container {{
                            background: rgba(255, 255, 255, 0.95);
                            backdrop-filter: blur(10px);
                            border-radius: 20px;
                            padding: 40px;
                            text-align: center;
                            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                            max-width: 400px;
                            color: #333;
                        }}
                        .success-icon {{
                            font-size: 4rem;
                            margin-bottom: 20px;
                            color: #22c55e;
                        }}
                        h2 {{
                            margin: 0 0 20px 0;
                            color: #1f2937;
                            font-size: 1.5rem;
                        }}
                        p {{
                            margin: 10px 0;
                            color: #6b7280;
                            line-height: 1.5;
                        }}
                        .loading {{
                            display: inline-block;
                            width: 20px;
                            height: 20px;
                            border: 3px solid #f3f3f3;
                            border-top: 3px solid #667eea;
                            border-radius: 50%;
                            animation: spin 1s linear infinite;
                            margin-left: 10px;
                        }}
                        @keyframes spin {{
                            0% {{ transform: rotate(0deg); }}
                            100% {{ transform: rotate(360deg); }}
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="success-icon">✅</div>
                        <h2>Authorization Successful!</h2>
                        <p>{message}</p>
                        <p>ComfyUI will refresh automatically<span class="loading"></span></p>
                    </div>
                    <script>
                        // Notify parent window (ComfyUI) about successful OAuth
                        if (window.opener) {{
                            try {{
                                window.opener.postMessage({{
                                    type: 'dropbox_oauth_complete',
                                    success: true,
                                    message: '{message}',
                                    session_id: '{session_id}'
                                }}, '*');
                                console.log('Sent OAuth completion message to parent window');
                            }} catch (e) {{
                                console.error('Could not notify parent window:', e);
                            }}
                        }}
                        
                        // Close this popup after a brief delay
                        setTimeout(() => {{
                            window.close();
                        }}, 2000);
                    </script>
                </body></html>
                """, content_type='text/html')
            else:
                return web.Response(text=f"""
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Dropbox Authorization Failed</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                            margin: 0;
                            padding: 40px 20px;
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                        }}
                        .container {{
                            background: rgba(255, 255, 255, 0.95);
                            backdrop-filter: blur(10px);
                            border-radius: 20px;
                            padding: 40px;
                            text-align: center;
                            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                            max-width: 400px;
                            color: #333;
                        }}
                        .error-icon {{
                            font-size: 4rem;
                            margin-bottom: 20px;
                            color: #ef4444;
                        }}
                        h2 {{
                            margin: 0 0 20px 0;
                            color: #1f2937;
                            font-size: 1.5rem;
                        }}
                        p {{
                            margin: 10px 0;
                            color: #6b7280;
                            line-height: 1.5;
                        }}
                        .retry-hint {{
                            background: #f3f4f6;
                            padding: 15px;
                            border-radius: 10px;
                            margin-top: 20px;
                            font-size: 0.9rem;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error-icon">❌</div>
                        <h2>Setup Failed</h2>
                        <p>{message}</p>
                        <div class="retry-hint">
                            <p>You can close this window and try again in ComfyUI.</p>
                        </div>
                    </div>
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