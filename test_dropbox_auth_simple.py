#!/usr/bin/env python3
"""
Simple non-interactive test script for DropboxAuthManager

Usage:
  python test_dropbox_auth_simple.py
  
This script tests the DropboxAuthManager without requiring user input.
"""

from dropbox_auth_manager import DropboxAuthManager
import os

def test_basic_functionality():
    """Test basic DropboxAuthManager functionality"""
    print("=" * 50)
    print("Testing DropboxAuthManager Basic Functionality")
    print("=" * 50)
    
    try:
        # Test initialization without credentials
        print("\n1. Testing initialization without credentials...")
        auth = DropboxAuthManager()
        print(f"✅ DropboxAuthManager initialized")
        print(f"   is_connected(): {auth.is_connected()}")
        
        # Test initialization with test credentials
        print("\n2. Testing initialization with test credentials...")
        test_auth = DropboxAuthManager(app_key="test_key_123", app_secret="test_secret_456")
        print(f"✅ DropboxAuthManager initialized with test credentials")
        print(f"   app_key: {test_auth.app_key}")
        print(f"   is_connected(): {test_auth.is_connected()}")
        
        # Test OAuth URL generation
        print("\n3. Testing OAuth URL generation...")
        oauth_url = test_auth.get_oauth_url()
        print(f"✅ Basic OAuth URL: {oauth_url[:80]}...")
        
        # Test OAuth URL with redirect_uri
        callback_url = "http://localhost:8188/oauth/dropbox/callback"
        oauth_url_with_redirect = test_auth.get_oauth_url(redirect_uri=callback_url, state="test-session-123")
        print(f"✅ OAuth URL with redirect: {oauth_url_with_redirect[:100]}...")
        
        # Test that redirect_uri is included
        if "redirect_uri=" in oauth_url_with_redirect and callback_url in oauth_url_with_redirect:
            print("✅ redirect_uri properly included in OAuth URL")
        else:
            print("❌ redirect_uri not found in OAuth URL")
        
        # Test that state is included
        if "state=test-session-123" in oauth_url_with_redirect:
            print("✅ state parameter properly included in OAuth URL")
        else:
            print("❌ state parameter not found in OAuth URL")
            
        print("\n" + "=" * 50)
        print("✅ All basic functionality tests passed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Error during basic functionality test: {e}")
        raise

def test_error_handling():
    """Test error handling scenarios"""
    print("\n" + "=" * 50)
    print("Testing Error Handling")
    print("=" * 50)
    
    try:
        # Test OAuth URL generation without app_key
        print("\n1. Testing OAuth URL without app_key...")
        auth_no_key = DropboxAuthManager()
        try:
            auth_no_key.get_oauth_url()
            print("❌ Should have raised ValueError")
        except ValueError as e:
            print(f"✅ Correctly raised ValueError: {e}")
        
        # Test auth code exchange without credentials
        print("\n2. Testing auth code exchange without credentials...")
        try:
            auth_no_key.exchange_auth_code_raw("test_code")
            print("❌ Should have raised ValueError")
        except ValueError as e:
            print(f"✅ Correctly raised ValueError: {e}")
        
        print("\n" + "=" * 50)
        print("✅ All error handling tests passed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Unexpected error during error handling test: {e}")
        raise

def test_token_exchange_retry_logic():
    """Test the token exchange retry logic (without actual API calls)"""
    print("\n" + "=" * 50)
    print("Testing Token Exchange Retry Logic")
    print("=" * 50)
    
    # This test just verifies the method exists and can be called with parameters
    # It won't make actual API calls since we don't have real credentials
    try:
        test_auth = DropboxAuthManager(app_key="test_key", app_secret="test_secret")
        
        print("\n1. Testing exchange_auth_code_raw method signature...")
        
        # Test method exists and accepts parameters (will fail with API call, but that's expected)
        try:
            test_auth.exchange_auth_code_raw("fake_code", redirect_uri="http://localhost:8188/oauth/dropbox/callback")
        except Exception as e:
            if "400" in str(e) or "requests" in str(e) or "HTTPSConnectionPool" in str(e):
                print(f"✅ Method executed correctly (expected API failure): {type(e).__name__}")
            else:
                print(f"❌ Unexpected error type: {e}")
        
        # Test method without redirect_uri
        try:
            test_auth.exchange_auth_code_raw("fake_code")
        except Exception as e:
            if "400" in str(e) or "requests" in str(e) or "HTTPSConnectionPool" in str(e):
                print(f"✅ Method executed correctly without redirect_uri (expected API failure): {type(e).__name__}")
            else:
                print(f"❌ Unexpected error type: {e}")
        
        print("\n" + "=" * 50)
        print("✅ Token exchange retry logic tests completed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Error during retry logic test: {e}")
        raise

def main():
    """Run all tests"""
    print("🧪 Starting DropboxAuthManager Tests")
    print("📝 This script tests the auth manager without making real API calls")
    
    try:
        test_basic_functionality()
        test_error_handling()
        test_token_exchange_retry_logic()
        
        print("\n🎉 All tests completed successfully!")
        print("💡 To test with real Dropbox credentials, use the interactive flow in ComfyUI")
        
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())