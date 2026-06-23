#!/bin/bash
set -euo pipefail

# Detect the Operating System
OS="$(uname)"

if [ "$OS" = "Darwin" ]; then
    # macOS-specific IP lookup
    export HOST_IP=$(ipconfig getifaddr en0)
elif [ "$OS" = "Linux" ]; then
    # Linux-specific IP lookup (grabs the primary local route IP)
    export HOST_IP=$(ip route get 1.0.0.1 2>/dev/null | awk '{print $7; exit}' || hostname -I | awk '{print $1}')
else
    echo "❌ Unsupported OS environment. Please set HOST_IP manually."
    exit 1
fi

# Fallback check if no IP was captured
if [ -z "$HOST_IP" ]; then
    echo "❌ Could not automatically detect your local IP address."
    echo "Ensure you are connected to Wi-Fi/LAN."
    exit 1
fi

echo "🚀 Launching Swiss TTS Monorepo on $OS..."
echo "📱 Mobile devices should connect to IP: $HOST_IP"

# Spin up Docker using the cross-platform variable
mise run docker-cleanup && mise run docker-compose

# Stream the logs for the interactive QR code
mise run docker-app-logs
