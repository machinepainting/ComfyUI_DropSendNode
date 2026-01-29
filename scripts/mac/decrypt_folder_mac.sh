#!/bin/bash

# DropSend Decryption Script for macOS
# Decrypts .enc files using a key stored in macOS Keychain

echo "=== DropSend File Decryption (macOS) ==="
echo ""
echo "Drag in the folder of files to decrypt, or type the path:"

# Read folder path (supports drag-and-drop)
read -r FOLDER
# Remove any surrounding quotes and trailing backslash from drag-and-drop
FOLDER=$(echo "$FOLDER" | sed "s/^['\"]//;s/['\"]$//;s/\\\\$//" | xargs)

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

# Retrieve key from Keychain
echo ""
echo "Retrieving key from Keychain..."
KEY=$(security find-generic-password -s "DropSend_Encryption_Key" -a "DropSend" -w 2>/dev/null)
if [ -z "$KEY" ]; then
    echo ""
    echo "Error: Failed to retrieve key from Keychain."
    echo ""
    echo "To store your encryption key in Keychain:"
    echo "  1. Open Keychain Access (search in Spotlight)"
    echo "  2. Click File > New Password Item"
    echo "  3. Set Keychain Item Name: DropSend_Encryption_Key"
    echo "  4. Set Account Name: DropSend"
    echo "  5. Set Password: [your encryption key]"
    echo "  6. Click Add"
    echo ""
    exit 1
fi
echo "Key retrieved successfully."
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
    # Default to .png if no other extension is apparent
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
