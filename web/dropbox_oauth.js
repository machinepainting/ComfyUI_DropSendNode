// dropbox_oauth.js - ComfyUI extension for seamless Dropbox OAuth flow

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Track OAuth popup windows
let oauthPopup = null;

app.registerExtension({
    name: "DropSendNode.OAuthHandler",
    
    async setup() {
        console.log("[DropSendNode] OAuth extension loaded");
        
        // Listen for WebSocket messages about OAuth completion
        api.addEventListener("dropbox_oauth_complete", (event) => {
            console.log("[DropSendNode] Received OAuth completion notification via WebSocket", event.detail);
            
            const data = event.detail;
            if (data.success) {
                console.log("[DropSendNode] OAuth successful - refreshing interface");
                this.handleOAuthSuccess();
            } else {
                console.error("[DropSendNode] OAuth failed:", data.message);
            }
        });
        
        // Listen for postMessage from OAuth popup window
        window.addEventListener("message", (event) => {
            if (event.data && event.data.type === 'dropbox_oauth_complete') {
                console.log("[DropSendNode] Received OAuth completion notification via postMessage", event.data);
                
                if (event.data.success) {
                    console.log("[DropSendNode] OAuth successful - refreshing interface");
                    this.handleOAuthSuccess();
                } else {
                    console.error("[DropSendNode] OAuth failed:", event.data.message);
                }
            }
        });
    },
    
    handleOAuthSuccess() {
        // Close OAuth popup if it's open
        if (oauthPopup && !oauthPopup.closed) {
            oauthPopup.close();
            console.log("[DropSendNode] Closed OAuth popup window");
        }
        
        // Refresh ComfyUI interface to update node UI
        setTimeout(() => {
            console.log("[DropSendNode] Refreshing ComfyUI interface");
            window.location.reload();
        }, 1500); // Small delay to ensure OAuth processing is complete
    },
    
    // Override node execution to detect and handle OAuth URLs
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "DropboxSetupNode") {
            console.log("[DropSendNode] Registered DropboxSetupNode enhancement");
            
            // Add custom OAuth popup handling
            const originalExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                console.log("[DropSendNode] Node executed with message:", message);
                
                // Check if this execution includes OAuth URL generation
                if (message && typeof message === 'object' && message.text && message.text[0]) {
                    const text = message.text[0];
                    if (text.includes('🚀 Automatic OAuth Ready!')) {
                        console.log("[DropSendNode] Detected automatic OAuth ready message");
                        
                        // Extract OAuth URL from the message
                        const urlMatch = text.match(/🔗 (https:\/\/www\.dropbox\.com\/oauth2\/authorize[^\s]+)/);
                        if (urlMatch) {
                            const oauthUrl = urlMatch[1];
                            console.log("[DropSendNode] Extracted OAuth URL:", oauthUrl);
                            
                            // Auto-open the popup after a brief delay
                            setTimeout(() => {
                                console.log("[DropSendNode] Auto-opening OAuth popup...");
                                window.openDropboxOAuth(oauthUrl);
                            }, 500);
                        }
                    }
                }
                
                if (originalExecuted) {
                    return originalExecuted.apply(this, arguments);
                }
            };
        }
    }
});

// Utility function to open OAuth in a small popup window
window.openDropboxOAuth = function(url) {
    console.log("[DropSendNode] Opening OAuth popup:", url);
    
    // Close existing popup if open
    if (oauthPopup && !oauthPopup.closed) {
        oauthPopup.close();
    }
    
    // Open small popup window
    const popup = window.open(
        url,
        'dropbox_oauth',
        'width=500,height=600,scrollbars=yes,resizable=yes,status=no,location=no,toolbar=no,menubar=no'
    );
    
    if (popup) {
        oauthPopup = popup;
        
        // Focus the popup
        popup.focus();
        
        // Monitor popup closure (optional - for fallback UI updates)
        const checkClosed = setInterval(() => {
            if (popup.closed) {
                console.log("[DropSendNode] OAuth popup closed by user");
                clearInterval(checkClosed);
                oauthPopup = null;
            }
        }, 1000);
        
        return popup;
    } else {
        console.error("[DropSendNode] Could not open OAuth popup - popup blocked?");
        return null;
    }
};