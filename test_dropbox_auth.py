#!/usr/bin/env python3
# test_dropbox_auth_simple.py - Non-interactive testing script for DropboxAuthManager

from dropbox_auth_manager import DropboxAuthManager

def test_oauth_url_generation():
    """Test OAuth URL generation"""
    print("🧪 TEST 1: OAuth URL generation")
    print("-" * 40)
    
    # Use a dummy app key for testing
    test_app_key = "test_app_key_12345"
    
    try:
        auth = DropboxAuthManager(app_key=test_app_key)
        oauth_url = auth.get_oauth_url()
        print(f"✅ Generated OAuth URL:")
        print(f"   {oauth_url}")
        expected_url = f"https://www.dropbox.com/oauth2/authorize?response_type=code&client_id={test_app_key}&token_access_type=offline"
        if oauth_url == expected_url:
            print("✅ URL format is correct")
            return True
        else:
            print("❌ URL format mismatch")
            return False
    except Exception as e:
        print(f"❌ Error generating OAuth URL: {e}")
        return False

def test_stored_credentials():
    """Test retrieving stored credentials"""
    print("\n🧪 TEST 2: Check for stored credentials")
    print("-" * 40)
    
    try:
        auth = DropboxAuthManager()
        
        print(f"App key stored: {bool(auth.app_key)}")
        print(f"App secret stored: {bool(auth.app_secret)}")  
        print(f"Refresh token stored: {bool(auth.refresh_token)}")
        print(f"Is connected: {auth.is_connected()}")
        
        if auth.is_connected():
            print("✅ Stored credentials found - testing access token...")
            try:
                access_token = auth.get_access_token()
                print(f"✅ Got access token: {access_token[:10]}...")
                return True
            except Exception as e:
                print(f"❌ Error getting access token: {e}")
                return False
        else:
            print("ℹ️ No stored credentials found (this is expected for first run)")
            return True
            
    except Exception as e:
        print(f"❌ Error checking stored credentials: {e}")
        return False

def test_auth_code_exchange():
    """Test auth code exchange with placeholder values"""
    print("\n🧪 TEST 3: Auth code exchange test (with dummy values)")
    print("-" * 40)
    
    # These are dummy values - replace with real ones to test
    test_app_key = "your_app_key_here"
    test_app_secret = "your_app_secret_here"  
    test_auth_code = "your_auth_code_here"
    
    if test_app_key == "your_app_key_here":
        print("ℹ️ Skipping auth code exchange test - placeholder values detected")
        print("ℹ️ To test this, replace the dummy values in this function with real credentials")
        return True
    
    try:
        auth = DropboxAuthManager(test_app_key, test_app_secret)
        print(f"Created DropboxAuthManager with app_key: {bool(auth.app_key)}, app_secret: {bool(auth.app_secret)}")
        
        auth.exchange_auth_code(test_auth_code)
        print("✅ Auth code exchange successful")
        print("✅ Credentials stored successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error during auth code exchange: {e}")
        return False

def test_manager_initialization():
    """Test DropboxAuthManager initialization with different parameters"""
    print("\n🧪 TEST 4: Manager initialization tests")
    print("-" * 40)
    
    try:
        # Test 1: Empty initialization
        auth1 = DropboxAuthManager()
        print(f"✅ Empty init - app_key: {auth1.app_key}, app_secret: {auth1.app_secret}")
        
        # Test 2: With parameters
        auth2 = DropboxAuthManager("test_key", "test_secret")
        print(f"✅ With params - app_key: {auth2.app_key}, app_secret: {auth2.app_secret}")
        
        # Test 3: With empty strings (this was causing the bug)
        auth3 = DropboxAuthManager("", "")
        print(f"✅ Empty strings - app_key: '{auth3.app_key}', app_secret: '{auth3.app_secret}'")
        
        return True
    except Exception as e:
        print(f"❌ Error during initialization tests: {e}")
        return False

def main():
    print("🚀 Dropbox Auth Manager Test Suite (Non-Interactive)")
    print("=" * 60)
    
    # Run all tests
    tests = [
        test_oauth_url_generation,
        test_stored_credentials, 
        test_manager_initialization,
        test_auth_code_exchange
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY:")
    passed = sum(results)
    total = len(results)
    print(f"✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️ Some tests failed - check output above")

if __name__ == "__main__":
    main()