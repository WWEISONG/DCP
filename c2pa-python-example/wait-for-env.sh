#!/bin/bash
# Wait for .env file to be created by local-setup and verify required keys exist

ENV_FILE="${ENV_FILE_PATH:-local_volume/.env}"
MAX_WAIT=120
WAIT_INTERVAL=2
ELAPSED=0

echo "Waiting for .env file at $ENV_FILE..."

# Wait for file to exist
while [ ! -f "$ENV_FILE" ] && [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
    echo "Still waiting for .env file... (${ELAPSED}s/${MAX_WAIT}s)"
done

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE after ${MAX_WAIT}s"
    exit 1
fi

echo ".env file found! Verifying required configuration..."

# Wait for required keys to be present
REQUIRED_KEYS=("KMS_KEY_ID" "CERT_CHAIN_PATH" "AWS_ACCESS_KEY_ID" "AWS_SECRET_ACCESS_KEY")
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    MISSING_KEYS=()
    for key in "${REQUIRED_KEYS[@]}"; do
        if ! grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
            MISSING_KEYS+=("$key")
        fi
    done
    
    if [ ${#MISSING_KEYS[@]} -eq 0 ]; then
        echo "All required configuration keys found!"
        break
    fi
    
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
    echo "Waiting for required keys: ${MISSING_KEYS[*]}... (${ELAPSED}s/${MAX_WAIT}s)"
done

# Final check
MISSING_KEYS=()
for key in "${REQUIRED_KEYS[@]}"; do
    if ! grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        MISSING_KEYS+=("$key")
    fi
done

if [ ${#MISSING_KEYS[@]} -gt 0 ]; then
    echo "ERROR: Missing required configuration keys: ${MISSING_KEYS[*]}"
    echo "Contents of $ENV_FILE:"
    cat "$ENV_FILE" || true
    exit 1
fi

echo "Configuration verified! Starting application..."
exec "$@"
