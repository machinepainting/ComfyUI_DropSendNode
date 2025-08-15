#!/usr/bin/env python3
# test_dropbox_auth.py - Manual testing script for DropboxAuthManager

from dropbox_auth_manager import DropboxAuthManager

def test_first_time_setup():
    """Test the initial auth code exchange flow"""
    print("🧪 STEP 1: First-time setup test")
    print("-" * 40)
    
    auth_code = input("Paste your Dropbox auth code: ").strip()
    app_key = input("App Key: ").strip()
    app_secret = input("App Secret: ").strip()

    print(f"Debug - app_key: '{app_key}' (len={len(app_key)})")
    print(f"Debug - app_secret: '{app_secret}' (len={len(app_secret)})")
    print(f"Debug - auth_code: '{auth_code}' (len={len(auth_code)})")

    auth = DropboxAuthManager(app_key, app_secret)

    try:
        auth.exchange_auth_code(auth_code)
        print("✅ Refresh token stored securely in system keyring.")
        return auth
    except Exception as e:
        print(f"❌ Error exchanging auth code: {e}")
        return None

def test_stored_credentials():
    """Test retrieving and using stored credentials"""
    print("\n🧪 STEP 2: Stored credentials test")
    print("-" * 40)
    
    try:
        # Test loading from keyring (no app_key/secret needed)
        auth = DropboxAuthManager()
        
        if not auth.is_connected():
            print("❌ No stored credentials found. Run first-time setup first.")
            return False
            
        print("✅ Stored credentials found.")
        
        # Test getting access token
        access_token = auth.get_access_token()
        print(f"✅ Got access token: {access_token[:10]}...")
        return True
        
    except Exception as e:
        print(f"❌ Error getting access token: {e}")
        return False

def test_oauth_url_generation():
    """Test OAuth URL generation"""
    print("\n🧪 STEP 3: OAuth URL generation test")
    print("-" * 40)
    
    app_key = input("App Key (for URL generation): ").strip()
    auth = DropboxAuthManager(app_key=app_key)
    
    try:
        oauth_url = auth.get_oauth_url()
        print(f"✅ Generated OAuth URL:")
        print(f"   {oauth_url}")
        print(f"   Copy this URL to authorize your app")
        return True
    except Exception as e:
        print(f"❌ Error generating OAuth URL: {e}")
        return False

def test_reset():
    """Test credential reset functionality"""
    print("\n🧪 STEP 4: Reset credentials test")
    print("-" * 40)
    
    confirm = input("Are you sure you want to clear stored credentials? (y/N): ").strip().lower()
    if confirm != 'y':
        print("⚠️ Skipping reset test.")
        return
        
    try:
        auth = DropboxAuthManager()
        auth.reset()
        print("✅ Credentials cleared from keyring.")
        
        # Verify they're actually gone
        auth_check = DropboxAuthManager()
        if not auth_check.is_connected():
            print("✅ Verified: No stored credentials found after reset.")
        else:
            print("❌ Warning: Credentials still found after reset.")
            
    except Exception as e:
        print(f"❌ Error during reset: {e}")

def main():
    print("🚀 Dropbox Auth Manager Test Suite")
    print("=" * 50)
    
    while True:
        print("\nSelect a test:")
        print("1. First-time setup (exchange auth code)")
        print("2. Test stored credentials")
        print("3. Generate OAuth URL")
        print("4. Reset stored credentials")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == "1":
            test_first_time_setup()
        elif choice == "2":
            test_stored_credentials()
        elif choice == "3":
            test_oauth_url_generation()
        elif choice == "4":
            test_reset()
        elif choice == "5":
            print("👋 Exiting test suite.")
            break
        else:
            print("❌ Invalid choice. Please select 1-5.")

if __name__ == "__main__":
    main()