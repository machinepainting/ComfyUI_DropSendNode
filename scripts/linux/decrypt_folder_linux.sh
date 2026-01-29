#!/bin/bash

# DropSend Decryption Script for Linux
# Decrypts .enc files using a key from environment variable or Secret Service

echo "=== DropSend File Decryption (Linux) ==="
echo ""
echo "Enter the folder path containing .enc files:"

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
echo "Would you like to decrypt files recursively (including subfolders)? (Y/N)"
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

# Python script to decrypt all .enc files
python3 - <<EOF
import os
import sys
from cryptography.fernet import Fernet

def decrypt_file(encrypted_path, output_path, key):
    try:
        fernet = Fernet(key.encode())
        with open(encrypted_path, 'rb') as enc_file:
            encrypted_data = enc_file.read()
        decrypted_data = fernet.decrypt(encrypted_data)
        with open(output_path, 'wb') as dec_file:
            dec_file.write(decrypted_data)
        print(f"  ✓ Decrypted: {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"  ✗ Error decrypting {os.path.basename(encrypted_path)}: {e}")
        return False

# Process .enc files
folder = "$FOLDER"
key = "$KEY"
recursive = "$RECURSIVE" == "true"

enc_files = []
success_count = 0
error_count = 0

print("Scanning for .enc files...")

if recursive:
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith('.enc'):
                enc_files.append(os.path.join(root, file))
else:
    for file in os.listdir(folder):
        if file.endswith('.enc'):
            enc_files.append(os.path.join(folder, file))

if not enc_files:
    print("No .enc files found in the specified location.")
    sys.exit(0)

print(f"Found {len(enc_files)} .enc file(s) to decrypt.")
print("")

for enc_path in enc_files:
    # Remove .enc extension to get original filename
    base_name = enc_path[:-4]  # Remove .enc
    if not os.path.splitext(base_name)[1]:
        # No extension found, default to .png
        out_path = base_name + '.png'
    else:
        out_path = base_name
    
    if decrypt_file(enc_path, out_path, key):
        success_count += 1
    else:
        error_count += 1

print("")
print(f"Decryption complete: {success_count} successful, {error_count} failed")
EOF

# Check if decryption was successful
if [ $? -ne 0 ]; then
    echo "Error: Decryption process encountered an error."
    exit 1
fi

echo ""

# Prompt to move .enc files
echo "Would you like to move all .enc files to a separate folder? (Y/N)"
read -r MOVE_RESPONSE
if [[ "$MOVE_RESPONSE" == "Y" || "$MOVE_RESPONSE" == "y" ]]; then
    ENC_FOLDER="$FOLDER/_encrypted_originals"
    mkdir -p "$ENC_FOLDER"
    MOVED_COUNT=0
    
    if [ "$RECURSIVE" = "true" ]; then
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                mv "$file" "$ENC_FOLDER/$(basename "$file")"
                ((MOVED_COUNT++))
            fi
        done < <(find "$FOLDER" -type f -name "*.enc" -print0)
    else
        for file in "$FOLDER"/*.enc; do
            if [ -f "$file" ]; then
                mv "$file" "$ENC_FOLDER/$(basename "$file")"
                ((MOVED_COUNT++))
            fi
        done
    fi
    
    echo "Moved $MOVED_COUNT .enc file(s) to: $ENC_FOLDER"
else
    echo "Leaving .enc files in place."
fi

echo ""
echo "Done!"
