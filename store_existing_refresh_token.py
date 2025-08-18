#!/usr/bin/env python3
"""
Store existing Dropbox refresh token directly in keyring

Use this if you already have working Dropbox credentials and want to store them securely.
"""

from dropbox_auth_manager import DropboxAuthManager

def store_existing_tokens():
    """Store existing tokens in keyring"""
    print("🔐 Store Existing Dropbox Tokens")
    print("=" * 40)
    
    # Your existing credentials
    app_key = "s9j8wbabc0jq8xr"
    app_secret = "t8s4xnsvhhxjwlb"  
    refresh_token = "Cz5dDuB9j1kAAAAAAAAAAZVGC0V3-vaLbl4Vcq9jneCQVOzwN0KhyeeBTN6D5VA8"
    
    try:
        # Create auth manager and store tokens
        auth_manager = DropboxAuthManager()
        auth_manager.store_tokens(app_key, app_secret, refresh_token)
        
        print("✅ Tokens stored successfully in keyring!")
        print(f"   App Key: {app_key}")
        print(f"   Refresh Token: {refresh_token[:20]}...")
        
        # Test that it works
        print("\n🧪 Testing stored credentials...")
        auth_test = DropboxAuthManager()
        
        if auth_test.is_connected():
            print("✅ Connection check passed!")
            
            # Try to get an access token
            access_token = auth_test.get_access_token()
            print(f"✅ Access token retrieved: {access_token[:20]}...")
            print("\n🎉 All credentials working perfectly!")
            
        else:
            print("❌ Connection check failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    store_existing_tokens()