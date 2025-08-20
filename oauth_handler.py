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
    
    def start_oauth_session(self, session_id, app_key, app_secret, completion_callback=None, storage_method="keyring", dropbox_folder="/Apps/ComfyUI_Output_Files", original_redirect_uri=None):
        """Start a new OAuth session and store the credentials for callback processing"""
        print(f"[OAuthHandler] Starting OAuth session: {session_id}")
        
        self.session_id = session_id
        self.app_key = app_key
        self.app_secret = app_secret
        self.completion_callback = completion_callback
        self.storage_method = storage_method
        self.dropbox_folder = dropbox_folder
        
        # Store in global pending sessions
        pending_oauth_sessions[session_id] = {
            'app_key': app_key,
            'app_secret': app_secret,
            'completion_callback': completion_callback,
            'storage_method': storage_method,
            'dropbox_folder': dropbox_folder,
            'original_redirect_uri': original_redirect_uri,  # Store the original redirect URI
            'handler': self
        }
        
        print(f"[OAuthHandler] OAuth session stored for: {session_id} with storage method: {storage_method}")
    
    async def process_callback(self, auth_code, redirect_uri=None):
        """Process the OAuth callback with the received auth code"""
        try:
            print(f"[OAuthHandler] Processing callback for session: {self.session_id}")
            print(f"[OAuthHandler] Auth code received: {auth_code[:10]}...")
            print(f"[OAuthHandler] Redirect URI: {redirect_uri}")
            
            # Use DropboxAuthManager to exchange the code
            print(f"[OAuthHandler] Creating DropboxAuthManager for token exchange...")
            auth_manager = DropboxAuthManager(self.app_key, self.app_secret)
            print(f"[OAuthHandler] Exchanging auth code for tokens...")
            result = auth_manager.exchange_auth_code_raw(auth_code, redirect_uri=redirect_uri)
            refresh_token = result.get("refresh_token")
            
            print(f"[OAuthHandler] Auth code exchange successful - got refresh token: {bool(refresh_token)}")
            print(f"[OAuthHandler] Using storage method: {self.storage_method}")
            
            # Handle different storage methods
            success_message = None
            if self.storage_method == "env_file":
                # Store in .env file
                import os
                node_dir = os.path.dirname(__file__)
                env_path = os.path.join(node_dir, ".env")
                with open(env_path, "w") as f:
                    f.write(f"DROPBOX_APP_KEY={self.app_key}\n")
                    f.write(f"DROPBOX_APP_SECRET={self.app_secret}\n")
                    f.write(f"DROPBOX_REFRESH_TOKEN={refresh_token}\n")
                    f.write(f"DROPBOX_FOLDER={self.dropbox_folder}\n")
                success_message = "Dropbox connected successfully! Credentials saved to .env file."
                
            elif self.storage_method == "display_only":
                # Display credentials for manual copying and create completion marker
                import os
                node_dir = os.path.dirname(__file__)
                display_marker_path = os.path.join(node_dir, ".dropbox_display_complete")
                with open(display_marker_path, "w") as f:
                    f.write("display_only_setup_completed")
                
                # Print credentials to console for easy copy/paste
                print("\n" + "=" * 80)
                print("DROPBOX CREDENTIALS READY FOR PRODUCTION - COPY FROM CONSOLE")
                print("=" * 80)
                print(f"DROPBOX_APP_KEY={self.app_key}")
                print(f"DROPBOX_APP_SECRET={self.app_secret}")
                print(f"DROPBOX_REFRESH_TOKEN={refresh_token}")
                print(f"DROPBOX_FOLDER={self.dropbox_folder}")
                print("=" * 80)
                print("Copy the lines above to your environment variables!")
                print("Perfect for RunPod, Docker, and production environments!")
                print("=" * 80 + "\n")
                
                success_message = f"""Dropbox Connected Successfully!

=====================================================================
ENVIRONMENT VARIABLES - Copy & Paste Ready
=====================================================================

DROPBOX_APP_KEY={self.app_key}

DROPBOX_APP_SECRET={self.app_secret}

DROPBOX_REFRESH_TOKEN={refresh_token}

DROPBOX_FOLDER={self.dropbox_folder}

=====================================================================
Perfect for RunPod, Docker, and production environments!
These credentials are ready to use immediately.
====================================================================="""
                
            else:
                # Fallback to env_file
                import os
                node_dir = os.path.dirname(__file__)
                env_path = os.path.join(node_dir, ".env")
                with open(env_path, "w") as f:
                    f.write(f"DROPBOX_APP_KEY={self.app_key}\n")
                    f.write(f"DROPBOX_APP_SECRET={self.app_secret}\n")
                    f.write(f"DROPBOX_REFRESH_TOKEN={refresh_token}\n")
                    f.write(f"DROPBOX_FOLDER={self.dropbox_folder}\n")
                success_message = "Dropbox connected successfully! Credentials saved to .env file."
            
            # Send WebSocket message to trigger ComfyUI refresh (except for display_only)
            if self.storage_method != "display_only":
                try:
                    from server import PromptServer
                    message_data = {
                        "type": "dropbox_oauth_complete",
                        "session_id": self.session_id,
                        "success": True,
                        "message": success_message
                    }
                    PromptServer.instance.send_sync("dropbox_oauth_complete", message_data)
                    print(f"[OAuthHandler] Sent WebSocket notification for OAuth completion")
                except Exception as e:
                    print(f"[OAuthHandler] Warning: Could not send WebSocket notification: {e}")
            else:
                print(f"[OAuthHandler] Skipping WebSocket notification for display_only method - no auto-refresh")
            
            # Call completion callback if provided
            if self.completion_callback:
                await self.completion_callback(True, success_message)
            
            return True, success_message
            
        except Exception as e:
            error_msg = f"Error: OAuth callback failed: {e}"
            print(f"[OAuthHandler] ERROR: {error_msg}")
            
            if self.completion_callback:
                await self.completion_callback(False, error_msg)
            
            return False, error_msg

def create_display_only_success_page(session_id, app_key, app_secret, refresh_token, dropbox_folder):
    """Create a success page with textarea fields for display_only storage method"""
    from aiohttp import web
    
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
                max-width: 600px;
                width: 90%;
                color: #333;
            }}
            .success-icon {{
                font-size: 4rem;
                margin-bottom: 20px;
                color: #22c55e;
            }}
            h2 {{
                margin: 0 0 10px 0;
                color: #1f2937;
                font-size: 1.5rem;
            }}
            h3 {{
                margin: 20px 0 15px 0;
                color: #374151;
                font-size: 1.1rem;
                text-align: left;
            }}
            .subtitle {{
                margin: 0 0 30px 0;
                color: #6b7280;
                line-height: 1.5;
                font-size: 0.95rem;
            }}
            .credential-group {{
                margin-bottom: 20px;
                text-align: left;
            }}
            .credential-label {{
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #374151;
                font-size: 0.9rem;
            }}
            .credential-input {{
                width: 100%;
                padding: 12px;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 0.85rem;
                background: #f9fafb;
                color: #1f2937;
                resize: none;
                box-sizing: border-box;
                transition: border-color 0.2s;
            }}
            .credential-input:focus {{
                outline: none;
                border-color: #3b82f6;
                background: white;
            }}
            .copy-button {{
                margin-top: 8px;
                padding: 6px 12px;
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 0.8rem;
                transition: background 0.2s;
            }}
            .copy-button:hover {{
                background: #2563eb;
            }}
            .copy-button:active {{
                background: #1d4ed8;
            }}
            .instructions {{
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 10px;
                padding: 20px;
                margin-top: 25px;
                text-align: left;
            }}
            .instructions h4 {{
                margin: 0 0 12px 0;
                color: #1e40af;
                font-size: 1rem;
            }}
            .instructions ol {{
                margin: 0;
                padding-left: 18px;
                color: #1e40af;
            }}
            .instructions li {{
                margin-bottom: 6px;
                line-height: 1.4;
            }}
            .auto-close-notice {{
                background: #f0fdf4;
                border: 1px solid #bbf7d0;
                border-radius: 8px;
                padding: 12px;
                margin-top: 20px;
                color: #166534;
                font-size: 0.85rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h2>Dropbox Connected Successfully!</h2>
            <p class="subtitle">Your credentials are ready for production use. Copy them to your environment variables.</p>
            
            <h3>🔐 Environment Variables</h3>
            
            <div class="credential-group">
                <label class="credential-label">DROPBOX_APP_KEY</label>
                <textarea class="credential-input" readonly onclick="this.select()" rows="1">{app_key}</textarea>
                <button class="copy-button" onclick="copyToClipboard(this.previousElementSibling)">📋 Copy</button>
            </div>
            
            <div class="credential-group">
                <label class="credential-label">DROPBOX_APP_SECRET</label>
                <textarea class="credential-input" readonly onclick="this.select()" rows="1">{app_secret}</textarea>
                <button class="copy-button" onclick="copyToClipboard(this.previousElementSibling)">📋 Copy</button>
            </div>
            
            <div class="credential-group">
                <label class="credential-label">DROPBOX_REFRESH_TOKEN</label>
                <textarea class="credential-input" readonly onclick="this.select()" rows="2">{refresh_token}</textarea>
                <button class="copy-button" onclick="copyToClipboard(this.previousElementSibling)">📋 Copy</button>
            </div>
            
            <div class="credential-group">
                <label class="credential-label">DROPBOX_FOLDER</label>
                <textarea class="credential-input" readonly onclick="this.select()" rows="1">{dropbox_folder}</textarea>
                <button class="copy-button" onclick="copyToClipboard(this.previousElementSibling)">📋 Copy</button>
            </div>
            
            <div class="instructions">
                <h4>📋 How to Use These Credentials</h4>
                <ol>
                    <li>Copy each environment variable above</li>
                    <li>Add them to your production environment (RunPod, Docker, etc.)</li>
                    <li>The ComfyUI DropSend node will detect and use them automatically</li>
                    <li>No additional setup required!</li>
                </ol>
            </div>
            
            <div class="auto-close-notice">
                📋 Copy the credentials above, then manually refresh ComfyUI to hide the auth fields. Close this window when done.
            </div>
        </div>
        
        <script>
            function copyToClipboard(textarea) {{
                textarea.select();
                textarea.setSelectionRange(0, 99999); // For mobile devices
                
                try {{
                    document.execCommand('copy');
                    
                    // Show success feedback
                    const button = textarea.nextElementSibling;
                    const originalText = button.textContent;
                    button.textContent = '✅ Copied!';
                    button.style.background = '#22c55e';
                    
                    setTimeout(() => {{
                        button.textContent = originalText;
                        button.style.background = '#3b82f6';
                    }}, 2000);
                }} catch (err) {{
                    console.error('Could not copy text: ', err);
                    alert('Copy failed. Please select the text manually.');
                }}
            }}
            
            // Auto-select text when clicking on textarea
            document.querySelectorAll('.credential-input').forEach(textarea => {{
                textarea.addEventListener('click', function() {{
                    this.select();
                }});
            }});
            
            // For display_only, don't auto-refresh ComfyUI - let user copy credentials first
            // The user can manually refresh when they're done
            console.log('Display-only OAuth completed - not auto-refreshing ComfyUI');
            
            // Don't auto-close for display_only - let user close manually after copying credentials
            // The user can close this window when they're done copying
        </script>
    </body>
    </html>
    """, content_type='text/html')

def get_server_base_url(request=None):
    """Dynamically detect the server base URL for OAuth callbacks"""
    import os
    import socket
    
    try:
        if request:
            # Try to get from the incoming request
            scheme = 'https' if request.secure else 'http'
            host = request.host
            base_url = f"{scheme}://{host}"
            print(f"[OAuthHandler] Detected server URL from request: {base_url}")
            return base_url
        else:
            # Fallback: try to detect from ComfyUI server instance
            from server import PromptServer
            if hasattr(PromptServer, 'instance') and PromptServer.instance:
                # Get the port from ComfyUI server
                port = getattr(PromptServer.instance, 'port', 8188)
                
                # Try to detect if we're on RunPod or similar cloud service
                hostname = socket.gethostname()
                print(f"[OAuthHandler] Detected hostname: {hostname}")
                
                # Check for RunPod-specific hostname patterns
                if 'runpod' in hostname.lower() or hostname.endswith('.runpod.net'):
                    # For RunPod, try to get the public URL
                    runpod_public_ip = os.getenv('RUNPOD_PUBLIC_IP')
                    if runpod_public_ip:
                        base_url = f"https://{runpod_public_ip}:{port}"
                        print(f"[OAuthHandler] Detected RunPod URL: {base_url}")
                        return base_url
                
                # Check for common cloud service environment variables
                public_url = os.getenv('COMFYUI_PUBLIC_URL') or os.getenv('PUBLIC_URL')
                if public_url:
                    base_url = public_url.rstrip('/')
                    print(f"[OAuthHandler] Using configured PUBLIC_URL: {base_url}")
                    return base_url
                
                # Default fallback to localhost
                base_url = f"http://localhost:{port}"
                print(f"[OAuthHandler] Fallback to localhost: {base_url}")
                return base_url
            
    except Exception as e:
        print(f"[OAuthHandler] Error detecting server URL: {e}")
        import traceback
        traceback.print_exc()
    
    # Final fallback
    base_url = "http://localhost:8188"
    print(f"[OAuthHandler] Using final fallback: {base_url}")
    return base_url

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
            
            # Use the original redirect URI that was used for authorization (not the detected one)
            original_callback_url = session_data.get('original_redirect_uri')
            if original_callback_url:
                print(f"[OAuthCallback] Using stored redirect URI: {original_callback_url}")
                callback_url = original_callback_url
            else:
                # Fallback to dynamic detection
                base_url = get_server_base_url(request)
                callback_url = f"{base_url}/oauth/dropbox/callback"
                print(f"[OAuthCallback] Using detected redirect URI: {callback_url}")
                
            success, message = await handler.process_callback(auth_code, redirect_uri=callback_url)
            
            # Clean up the session
            del pending_oauth_sessions[session_id]
            
            if success:
                # Check if this is a display_only flow and show appropriate success page
                storage_method = session_data.get('storage_method', 'keyring')
                
                if storage_method == 'display_only':
                    # Extract refresh token from the success message (token exchange already happened in process_callback)
                    if 'DROPBOX_REFRESH_TOKEN=' in message:
                        import re
                        refresh_token_match = re.search(r'DROPBOX_REFRESH_TOKEN=([^\s\n]+)', message)
                        if refresh_token_match:
                            refresh_token = refresh_token_match.group(1)
                            
                            app_key = session_data['app_key']
                            app_secret = session_data['app_secret'] 
                            dropbox_folder = session_data['dropbox_folder']
                            
                            # Special success page with textarea fields for credentials
                            return create_display_only_success_page(session_id, app_key, app_secret, refresh_token, dropbox_folder)
                    
                    # If we couldn't extract the refresh token, fall back to error handling
                    return web.Response(text=f"""
                    <html><body>
                        <h2>❌ Display Setup Error</h2>
                        <p>Could not extract refresh token from OAuth response.</p>
                        <p>Please close this window and try again in ComfyUI.</p>
                        <p>Debug info: {message[:200]}...</p>
                    </body></html>
                    """, content_type='text/html', status=500)
                else:
                    # Standard success page for other storage methods
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
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Dropbox Authorization Code</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%);
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
                        max-width: 500px;
                        color: #333;
                    }}
                    .code-icon {{
                        font-size: 4rem;
                        margin-bottom: 20px;
                        color: #3b82f6;
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
                    .auth-code {{
                        background: #f3f4f6;
                        padding: 20px;
                        border-radius: 10px;
                        margin: 20px 0;
                        font-family: 'Monaco', 'Menlo', monospace;
                        font-size: 1.1rem;
                        word-break: break-all;
                        color: #1f2937;
                        border: 2px solid #3b82f6;
                        position: relative;
                    }}
                    .copy-hint {{
                        background: #eff6ff;
                        padding: 15px;
                        border-radius: 10px;
                        margin-top: 20px;
                        font-size: 0.9rem;
                        color: #1e40af;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="code-icon">🔄</div>
                    <h2>Authorization Code Received</h2>
                    <p>Please return to ComfyUI and manually enter this code:</p>
                    <div class="auth-code">{auth_code}</div>
                    <div class="copy-hint">
                        <p>📋 Select the code above and copy it to ComfyUI</p>
                    </div>
                </div>
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