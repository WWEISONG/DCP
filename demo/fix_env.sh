#!/bin/bash
# Fix the .env file by re-running the setup
# This script will remove the existing .env file and re-run local-setup

C2PA_DIR="/mnt/data3/weisong/Haonan/VideoMark/c2pa-python-example"
ENV_FILE="${C2PA_DIR}/local_volume/.env"

echo "Fixing .env file by re-running setup..."
echo ""

# Check if .env exists
if [ -f "$ENV_FILE" ]; then
    echo "Backing up existing .env file..."
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Removing existing .env file to force re-setup..."
    rm "$ENV_FILE"
else
    echo ".env file does not exist - setup will create it"
fi

echo ""
echo "Ensuring localstack is running and healthy..."
cd "$C2PA_DIR"
# Start localstack if not running
sudo docker compose up -d localstack-main

# Wait for localstack to be healthy
echo "Waiting for localstack to be ready..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    HEALTH=$(sudo docker compose ps localstack-main --format json 2>/dev/null | grep -o '"Health":"[^"]*"' | cut -d'"' -f4 || echo "")
    if [ "$HEALTH" = "healthy" ]; then
        echo "Localstack is healthy!"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    if [ $((WAITED % 10)) -eq 0 ]; then
        echo "Waiting for localstack... (${WAITED}s/${MAX_WAIT}s)"
    fi
done

if [ "$HEALTH" != "healthy" ]; then
    echo "WARNING: Localstack may not be ready, but proceeding with setup..."
fi

echo ""
echo "Re-running local-setup container..."
# docker compose run automatically joins the network defined in docker-compose.yaml
sudo docker compose run --rm local-setup

echo ""
echo "Checking if .env file was created with required keys..."
if [ -f "$ENV_FILE" ]; then
    if grep -q "^KMS_KEY_ID=" "$ENV_FILE" && grep -q "^AWS_SECRET_ACCESS_KEY=" "$ENV_FILE"; then
        echo "✓ .env file created successfully with required keys!"
        echo ""
        echo "You can now restart the signer:"
        echo "  sudo docker compose restart local-signer"
    else
        echo "✗ .env file exists but is missing required keys"
        echo "Check the setup logs above for errors"
    fi
else
    echo "✗ .env file was not created"
    echo "Check the setup logs above for errors"
fi
