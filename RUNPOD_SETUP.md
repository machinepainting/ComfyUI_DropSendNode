# RunPod OAuth Setup Guide

## Quick Setup for RunPod

The DropSend node now automatically detects RunPod environments, but for OAuth to work properly, you may need to configure your public URL.

### Option 1: Automatic Detection (Try This First)

The node will try to automatically detect your RunPod URL. Just run the OAuth flow and check the console for messages like:

```
[OAuthHandler] Detected server URL from request: https://your-runpod-url.runpod.net
```

### Option 2: Manual Configuration (If Auto-Detection Fails)

If the automatic detection doesn't work, set one of these environment variables:

#### Method A: Set PUBLIC_URL Environment Variable
```bash
export PUBLIC_URL="https://your-runpod-id.runpod.net:8188"
```

#### Method B: Set COMFYUI_PUBLIC_URL Environment Variable
```bash
export COMFYUI_PUBLIC_URL="https://your-runpod-id.runpod.net:8188"
```

### How to Find Your RunPod URL

1. **From RunPod Dashboard**: Look for your pod's public URL
2. **From Browser**: Copy the URL you use to access ComfyUI
3. **From Console**: The node will log detected URLs during OAuth

### Example URLs

- `https://abc123-8188.proxy.runpod.net`
- `https://xyz789.runpod.net:8188`
- `https://your-custom-domain.com:8188`

### Testing the Configuration

1. Run the DropboxSetupNode
2. Check console output for detected URL
3. If URL looks wrong, set the environment variable and restart ComfyUI

### Troubleshooting

**Problem**: OAuth callback fails with "redirect_uri mismatch"
**Solution**: Check that the detected URL in the console matches how you access ComfyUI

**Problem**: Automatic detection shows localhost
**Solution**: Set PUBLIC_URL or COMFYUI_PUBLIC_URL environment variable

**Problem**: Still getting localhost after setting environment variables
**Solution**: Restart ComfyUI after setting environment variables

### Storage Method Recommendations for RunPod

1. **`keyring`**: Now works with encrypted file storage (recommended)
2. **`display_only`**: Best for temporary pods - copy credentials to environment
3. **`env_file`**: Good for persistent storage volumes

## 💡 Tips

- The enhanced keyring backend now works on RunPod with encrypted file storage
- Use `display_only` for maximum flexibility in cloud environments
- Set environment variables in your RunPod template for automatic configuration
