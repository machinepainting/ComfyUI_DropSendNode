#!/bin/bash

# DropSend Encryption Script for Linux
# Encrypts image/video files using a key from environment variable or Secret Service

echo "=== DropSend File Encryption (Linux) ==="
echo ""
echo "Enter the folder path containing files to encrypt:"

# Read folder path
read -r FOLDER
# Remove any surrounding quotes
FOLDER=$(echo "$FOLDER" | sed "s/^['\"]//;s/['\"]$//")

# Validate folder path
if [ -z "$FOLDER" ] || [ ! -d "$FOLDER" ]; then
    echo "Error: '$FOLDER' is not a valid directory."
    exit 1
fi

echo "Processing folder: $FOLDER"
echo ""

# Prompt for recursive option
echo "Would you like to encrypt files recursively (including subfolders)? (Y/N)"
read -r RECURSIVE_RESPONSE
if [[ "$RECURSIVE_RESPONSE" == "Y" || "$RECURSIVE_RESPONSE" == "y" ]]; then
    RECURSIVE="true"
else
    RECURSIVE="false"
fi

# Try to get key from environment variable
echo ""
echo "Retrieving encryption key..."

KEY="${DROPSEND_ENCRYPTION_KEY:-}"

# If not in environment, try secret-tool (GNOME Keyring / KWallet)
if [ -z "$KEY" ] && command -v secret-tool &> /dev/null; then
    KEY=$(secret-tool lookup service DropSend username DropSend 2>/dev/null)
    if [ -n "$KEY" ]; then
        echo "Using key from Secret Service (GNOME Keyring/KWallet)."
    fi
fi

# If still no key, prompt user
if [ -z "$KEY" ]; then
    echo ""
    echo "Encryption key not found in environment or Secret Service."
    echo ""
    echo "To set up automatic key retrieval, either:"
    echo "  1. Set environment variable: export DROPSEND_ENCRYPTION_KEY=\"your_key\""
    echo "  2. Store with secret-tool: echo -n \"your_key\" | secret-tool store --label=\"DropSend\" service DropSend username DropSend"
    echo ""
    echo -n "Enter your encryption key: "
    read -r KEY
    
    if [ -z "$KEY" ]; then
        echo "Error: No key provided."
        exit 1
    fi
else
    echo "Key retrieved successfully."
fi

echo ""

# Python script to encrypt supported files
python3 - <<EOF
import os
import sys
from cryptography.fernet import Fernet

# Supported file extensions (matching DropSend node)
SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.avi', '.mov')

def encrypt_file(input_path, output_path, key):
    try:
        fernet = Fernet(key.encode())
        with open(input_path, 'rb') as in_file:
            data = in_file.read()
        encrypted_data = fernet.encrypt(data)
        with open(output_path, 'wb') as out_file:
            out_file.write(encrypted_data)
        return True
    except Exception as e:
        print(f"  ✗ Error encrypting {os.path.basename(input_path)}: {e}")
        return False

# Process files
folder = "$FOLDER"
key = "$KEY"
recursive = "$RECURSIVE" == "true"

files_to_encrypt = []
success_count = 0
error_count = 0

print("Scanning for supported files...")
print(f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
print("")

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

for file_path in files_to_encrypt:
    # Create temp file first, then rename
    temp_enc_path = file_path + '.tmp.enc'
    final_enc_path = file_path + '.enc'
    
    try:
        if encrypt_file(file_path, temp_enc_path, key):
            os.remove(file_path)  # Delete original
            os.rename(temp_enc_path, final_enc_path)  # Rename to final
            print(f"  ✓ Encrypted: {os.path.basename(file_path)} → {os.path.basename(final_enc_path)}")
            success_count += 1
        else:
            error_count += 1
            if os.path.exists(temp_enc_path):
                os.remove(temp_enc_path)
    except Exception as e:
        print(f"  ✗ Error processing {os.path.basename(file_path)}: {e}")
        error_count += 1
        if os.path.exists(temp_enc_path):
            os.remove(temp_enc_path)

print("")
print(f"Encryption complete: {success_count} successful, {error_count} failed")
EOF

# Check if encryption was successful
if [ $? -ne 0 ]; then
    echo "Error: Encryption process encountered an error."
    exit 1
fi

echo ""
echo "Done!"
