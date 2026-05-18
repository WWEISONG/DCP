#!/bin/bash
# Fix permissions for client_volume directory
# This script needs to be run with sudo or by a user with appropriate permissions

C2PA_DIR="/mnt/data3/weisong/Haonan/VideoMark/c2pa-python-example"
CLIENT_VOLUME="${C2PA_DIR}/client_volume"

echo "Fixing permissions for ${CLIENT_VOLUME}..."

# Get current user
CURRENT_USER=${SUDO_USER:-$USER}
CURRENT_GROUP=$(id -gn $CURRENT_USER)

echo "Setting ownership to ${CURRENT_USER}:${CURRENT_GROUP}"

# Change ownership
sudo chown -R ${CURRENT_USER}:${CURRENT_GROUP} "${CLIENT_VOLUME}" 2>/dev/null || {
    echo "ERROR: Could not change ownership. Please run this script with sudo:"
    echo "  sudo $0"
    exit 1
}

# Set permissions
sudo chmod -R 755 "${CLIENT_VOLUME}" 2>/dev/null || {
    echo "WARNING: Could not set permissions"
}

# Create subdirectories if they don't exist
sudo mkdir -p "${CLIENT_VOLUME}/input-images"
sudo mkdir -p "${CLIENT_VOLUME}/signed-images"

# Set ownership on subdirectories
sudo chown -R ${CURRENT_USER}:${CURRENT_GROUP} "${CLIENT_VOLUME}/input-images"
sudo chown -R ${CURRENT_USER}:${CURRENT_GROUP} "${CLIENT_VOLUME}/signed-images"

echo "Permissions fixed successfully!"
echo "Directory: ${CLIENT_VOLUME}"
ls -la "${CLIENT_VOLUME}"
