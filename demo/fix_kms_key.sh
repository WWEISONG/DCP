#!/bin/bash
# Script to fix missing KMS key in LocalStack

cd "$(dirname "$0")/../c2pa-python-example" || exit 1

echo "Checking if LocalStack is running..."
if ! sudo docker compose ps localstack-main 2>/dev/null | grep -q "Running"; then
    echo "LocalStack is not running. Starting it..."
    cd "$(dirname "$0")/../c2pa-python-example" || exit 1
    sudo docker compose up -d localstack-main
    
    echo "Waiting for LocalStack to be ready..."
    sleep 5
    
    # Wait for LocalStack to be healthy (up to 60 seconds)
    max_wait=60
    waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -f -s http://localhost:4566/_localstack/health >/dev/null 2>&1; then
            echo "✓ LocalStack is ready"
            break
        fi
        sleep 2
        waited=$((waited + 2))
        if [ $((waited % 10)) -eq 0 ]; then
            echo "  Still waiting... (${waited}s/${max_wait}s)"
        fi
    done
    
    if [ $waited -ge $max_wait ]; then
        echo "WARNING: LocalStack did not become ready after ${max_wait} seconds"
        echo "Continuing anyway..."
    fi
fi

echo "Re-running local-setup to recreate KMS key..."
sudo docker compose run --rm local-setup

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Setup completed successfully!"
    echo "KMS key should now be available in LocalStack."
else
    echo ""
    echo "✗ Setup failed. Check the error messages above."
    exit 1
fi
