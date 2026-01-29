#!/usr/bin/env python3
"""
DropSend Encryption Script for Windows
Encrypts image/video files using a key from environment variable or manual input

NOTE: This script is for LOCAL USE ONLY - for encrypting files on your local machine
outside of ComfyUI. The DropSend node handles encryption automatically during upload.
"""

import os
import sys

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("Error: cryptography library not installed.")
    print("Run: pip install cryptography")
    sys.exit(1)


# Supported file extensions (matching DropSend node)
SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.avi', '.mov')


def get_encryption_key():
    """Get encryption key from environment variable or user input."""
    # Try environment variable first
    key = os.environ.get('DROPSEND_ENCRYPTION_KEY')
    if key:
        print("Using key from DROPSEND_ENCRYPTION_KEY environment variable.")
        return key
    
    # Prompt user
    print("")
    print("Encryption key not found in environment.")
    print("")
    print("To set up automatic key retrieval:")
    print("  1. Press Win + R, type 'sysdm.cpl', press Enter")
    print("  2. Go to Advanced tab > Environment Variables")
    print("  3. Under User variables, click New")
    print("  4. Variable name: DROPSEND_ENCRYPTION_KEY")
    print("  5. Variable value: [your encryption key]")
    print("  6. Click OK and restart any open terminals")
    print("")
    key = input("Enter your encryption key: ").strip()
    
    if not key:
        print("Error: No key provided.")
        sys.exit(1)
    
    return key


def encrypt_file(input_path, output_path, fernet):
    """Encrypt a single file."""
    try:
        with open(input_path, 'rb') as in_file:
            data = in_file.read()
        encrypted_data = fernet.encrypt(data)
        with open(output_path, 'wb') as out_file:
            out_file.write(encrypted_data)
        return True
    except Exception as e:
        print(f"  X Error encrypting {os.path.basename(input_path)}: {e}")
        return False


def main():
    print("=== DropSend File Encryption (Windows) ===")
    print("")
    print("NOTE: This script is for LOCAL USE ONLY.")
    print("The DropSend node handles encryption automatically during upload.")
    print("")
    
    # Get folder path
    folder = input("Enter the folder path containing files to encrypt: ").strip()
    # Remove surrounding quotes if present
    folder = folder.strip('"\'')
    
    if not folder or not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a valid directory.")
        sys.exit(1)
    
    print(f"Processing folder: {folder}")
    print("")
    
    # Recursive option
    recursive_input = input("Encrypt files recursively (including subfolders)? (Y/N): ").strip().upper()
    recursive = recursive_input == 'Y'
    
    # Get encryption key
    print("")
    key = get_encryption_key()
    
    try:
        fernet = Fernet(key.encode())
    except Exception as e:
        print(f"Error: Invalid encryption key format: {e}")
        sys.exit(1)
    
    print("")
    print("Scanning for supported files...")
    print(f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
    print("")
    
    # Find all supported files
    files_to_encrypt = []
    if recursive:
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    files_to_encrypt.append(os.path.join(root, file))
    else:
        for file in os.listdir(folder):
            if file.lower().endswith(SUPPORTED_EXTENSIONS):
                files_to_encrypt.append(os.path.join(folder, file))
    
    if not files_to_encrypt:
        print("No supported files found in the specified location.")
        sys.exit(0)
    
    print(f"Found {len(files_to_encrypt)} file(s) to encrypt.")
    print("")
    
    success_count = 0
    error_count = 0
    
    for file_path in files_to_encrypt:
        temp_enc_path = file_path + '.tmp.enc'
        final_enc_path = file_path + '.enc'
        
        try:
            if encrypt_file(file_path, temp_enc_path, fernet):
                os.remove(file_path)  # Delete original
                os.rename(temp_enc_path, final_enc_path)  # Rename to final
                print(f"  + Encrypted: {os.path.basename(file_path)} -> {os.path.basename(final_enc_path)}")
                success_count += 1
            else:
                error_count += 1
                if os.path.exists(temp_enc_path):
                    os.remove(temp_enc_path)
        except Exception as e:
            print(f"  X Error processing {os.path.basename(file_path)}: {e}")
            error_count += 1
            if os.path.exists(temp_enc_path):
                os.remove(temp_enc_path)
    
    print("")
    print(f"Encryption complete: {success_count} successful, {error_count} failed")
    print("")
    print("Done!")


if __name__ == "__main__":
    main()
