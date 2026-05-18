#!/bin/bash
# Enable verbose output for debugging
# Redirect stderr to stdout so we can see all output
exec 2>&1

echo "=== Starting local-setup.sh ==="
echo "Script location: $0"
echo "Current directory: $(pwd)"
echo "User: $(whoami)"
echo ""

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    echo "ERROR: setup.py not found. Current directory contents:"
    ls -la
    exit 1
fi

echo "Contents of current directory:"
ls -la | head -20
echo ""

# Check required tools
echo "Checking required tools..."
which python3 || echo "WARNING: python3 not found"
which awslocal || echo "WARNING: awslocal not found"
which jq || echo "WARNING: jq not found"
which openssl || echo "WARNING: openssl not found"
which curl || echo "WARNING: curl not found"
echo ""

# Now enable strict error handling, but we'll handle expected errors
set -e

# Check if .env exists and has all required keys
REQUIRED_KEYS=("KMS_KEY_ID" "CERT_CHAIN_PATH" "AWS_ACCESS_KEY_ID" "AWS_SECRET_ACCESS_KEY")
NEEDS_SETUP=true

if [[ -e local_volume/.env ]]; then
    echo "local_volume/.env already exists. Checking for required keys..."
    MISSING_KEYS=()
    for key in "${REQUIRED_KEYS[@]}"; do
        if ! grep -q "^${key}=" local_volume/.env; then
            MISSING_KEYS+=("$key")
        fi
    done
    
    if [ ${#MISSING_KEYS[@]} -eq 0 ]; then
        echo "All required keys found in .env file. Verifying KMS key exists in LocalStack..."
        
        # Extract KMS_KEY_ID from .env
        KMS_KEY_ID_VALUE=$(grep "^KMS_KEY_ID=" local_volume/.env | cut -d'=' -f2 | tr -d "'\"")
        
        if [ -n "$KMS_KEY_ID_VALUE" ]; then
            # Wait a bit for LocalStack to be ready before checking
            sleep 2
            
            # Check if key actually exists in LocalStack
            echo "Checking if KMS key $KMS_KEY_ID_VALUE exists in LocalStack..."
            if awslocal --endpoint-url=http://localstack-main:4566 kms describe-key --key-id "$KMS_KEY_ID_VALUE" >/dev/null 2>&1; then
                echo "✓ KMS key verified in LocalStack. Setup already complete."
                exit 0
            else
                echo "WARNING: KMS key $KMS_KEY_ID_VALUE not found in LocalStack!"
                echo "LocalStack may have been restarted and lost the key."
                echo "Re-running setup to recreate the key..."
                # Backup and remove .env to force re-setup
                cp local_volume/.env local_volume/.env.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
                rm local_volume/.env
                NEEDS_SETUP=true
            fi
        else
            echo "KMS_KEY_ID found in .env but value is empty. Re-running setup..."
            cp local_volume/.env local_volume/.env.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
            rm local_volume/.env
            NEEDS_SETUP=true
        fi
    else
        echo "WARNING: .env file exists but is missing required keys: ${MISSING_KEYS[*]}"
        echo "Backing up existing .env file and re-running setup..."
        cp local_volume/.env local_volume/.env.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
        rm local_volume/.env
    fi
fi

if [ "$NEEDS_SETUP" = true ]; then
    echo "Starting setup"
    
    # Wait for localstack to be ready and accessible
    echo "Waiting for localstack to be ready..."
    MAX_WAIT=90
    WAITED=0
    while [ $WAITED -lt $MAX_WAIT ]; do
        # Try to connect to localstack-main (service name in docker-compose)
        if curl -f -s http://localstack-main:4566/_localstack/health >/dev/null 2>&1; then
            echo "Localstack health check passed!"
            # Verify the endpoint is accessible (we don't need AWS credentials yet)
            # Just check that we can reach the service
            if curl -f -s http://localstack-main:4566 >/dev/null 2>&1; then
                echo "Localstack-main is ready and accessible!"
                break
            fi
        fi
        sleep 3
        WAITED=$((WAITED + 3))
        if [ $((WAITED % 15)) -eq 0 ]; then
            echo "Waiting for localstack-main... (${WAITED}s/${MAX_WAIT}s)"
            # Try to diagnose the issue
            if ! ping -c 1 localstack-main >/dev/null 2>&1; then
                echo "  Warning: Cannot ping localstack-main hostname - network issue?"
            fi
        fi
    done
    
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "ERROR: Localstack did not become ready after ${MAX_WAIT} seconds"
        echo "Diagnostics:"
        echo "  - Checking if localstack container is running..."
        docker ps | grep localstack || echo "    Localstack container not found"
        echo "  - Checking network connectivity..."
        ping -c 2 localstack-main 2>&1 || echo "    Cannot resolve localstack-main hostname"
        echo "  - Checking if port 4566 is accessible..."
        curl -v http://localstack-main:4566/_localstack/health 2>&1 | head -5 || echo "    Cannot connect to localstack-main"
        echo ""
        echo "Please ensure localstack container is running: docker compose ps localstack-main"
        exit 1
    fi
    
    echo "Creating a test user in localstack"
    # Create user, but don't fail if it already exists
    set +e  # Temporarily disable exit on error
    USER_OUTPUT=$(awslocal --endpoint-url=http://localstack-main:4566 iam create-user --user-name test 2>&1)
    USER_EXIT_CODE=$?
    set -e  # Re-enable exit on error
    
    if [ $USER_EXIT_CODE -ne 0 ]; then
        if echo "$USER_OUTPUT" | grep -qi "EntityAlreadyExists\|already exists"; then
            echo "User 'test' already exists, continuing..."
        else
            echo "WARNING: Could not create user: $USER_OUTPUT"
            echo "Attempting to verify user exists..."
            set +e
            awslocal --endpoint-url=http://localstack-main:4566 iam get-user --user-name test >/dev/null 2>&1
            GET_USER_EXIT=$?
            set -e
            if [ $GET_USER_EXIT -ne 0 ]; then
                echo "ERROR: User 'test' does not exist and could not be created"
                exit 1
            fi
            echo "User 'test' exists, proceeding..."
        fi
    else
        echo "User 'test' created successfully"
    fi

    # Add AWS_ENDPOINT and RUN_MODE to .env.local FIRST (required by setup.py)
    echo "Adding AWS configuration to .env.local..."
    echo "AWS_ENDPOINT=http://localstack-main:4566" > .env.local
    echo "RUN_MODE=DEV" >> .env.local
    echo "REGION=us-east-1" >> .env.local
    
    echo "Creating test credentials in localstack and saving them to .env.local file"
    # Check if .env file exists and has AWS credentials, use those if available
    if [[ -e ../.env ]] && grep -q "^AWS_ACCESS_KEY_ID=" ../.env && grep -q "^AWS_SECRET_ACCESS_KEY=" ../.env; then
        echo "Using AWS credentials from .env file"
        grep "^AWS_ACCESS_KEY_ID=" ../.env >> .env.local
        grep "^AWS_SECRET_ACCESS_KEY=" ../.env >> .env.local
    else
        # Create new credentials if .env doesn't have them
        echo "Creating new AWS credentials..."
        # Try multiple times in case localstack is still starting
        MAX_RETRIES=5
        RETRY=0
        while [ $RETRY -lt $MAX_RETRIES ]; do
            ACCESS_KEY_OUTPUT=$(awslocal --endpoint-url=http://localstack-main:4566 iam create-access-key --user-name test --output json 2>&1)
            if [ $? -eq 0 ]; then
                echo "$ACCESS_KEY_OUTPUT" | jq -r '.AccessKey | "AWS_ACCESS_KEY_ID=\(.AccessKeyId)\nAWS_SECRET_ACCESS_KEY=\(.SecretAccessKey)"' >> .env.local
                echo "Successfully created AWS credentials"
                break
            else
                RETRY=$((RETRY + 1))
                if [ $RETRY -lt $MAX_RETRIES ]; then
                    echo "Retry $RETRY/$MAX_RETRIES: Waiting for localstack... ($ACCESS_KEY_OUTPUT)"
                    sleep 3
                else
                    echo "ERROR: Failed to create access key after $MAX_RETRIES attempts: $ACCESS_KEY_OUTPUT"
                    echo "Checking localstack-main connectivity..."
                    ping -c 2 localstack-main || echo "Cannot ping localstack-main - network issue?"
                    exit 1
                fi
            fi
        done
    fi

    echo "Creating KMS key in localstack"
    # Set ENV_FILE_PATH so setup.py writes KMS_KEY_ID to .env.local (which will be copied to local_volume/.env)
    # Pass .env.local as the env_file_path parameter to ensure it writes there
    echo "Running: python setup.py create-key-and-csr 'CN=John Smith,O=C2PA Python Demo' .env.local"
    if ! python setup.py create-key-and-csr 'CN=John Smith,O=C2PA Python Demo' .env.local; then
        echo "ERROR: setup.py failed. Check the error above."
        echo "Contents of .env.local so far:"
        cat .env.local || true
        exit 1
    fi
    
    # Verify KMS_KEY_ID was added
    if ! grep -q "^KMS_KEY_ID=" .env.local; then
        echo "WARNING: KMS_KEY_ID was not added to .env.local by setup.py"
        echo "Attempting to extract from setup.py output or .env file..."
        # Try to get it from the root .env if it was written there
        if [ -f .env ] && grep -q "^KMS_KEY_ID=" .env; then
            grep "^KMS_KEY_ID=" .env >> .env.local
            echo "Copied KMS_KEY_ID from .env to .env.local"
        else
            echo "ERROR: Could not find KMS_KEY_ID. Setup may have failed."
            echo "Contents of .env.local:"
            cat .env.local
            exit 1
        fi
    else
        echo "KMS_KEY_ID successfully added to .env.local"
        
        # Verify the key actually exists in LocalStack
        KMS_KEY_ID_VALUE=$(grep "^KMS_KEY_ID=" .env.local | cut -d'=' -f2 | tr -d "'\"")
        echo "Verifying KMS key exists in LocalStack: $KMS_KEY_ID_VALUE"
        
        # Try to describe the key
        if awslocal --endpoint-url=http://localstack-main:4566 kms describe-key --key-id "$KMS_KEY_ID_VALUE" >/dev/null 2>&1; then
            echo "✓ KMS key verified in LocalStack"
        else
            echo "WARNING: KMS key $KMS_KEY_ID_VALUE not found in LocalStack!"
            echo "Listing all keys in LocalStack:"
            awslocal --endpoint-url=http://localstack-main:4566 kms list-keys || echo "Could not list keys"
            echo "This may indicate the key creation failed silently."
        fi
    fi

    # We should use some default values for the root CA certificate
    echo "Creating root CA certificate"
    openssl req -x509 \
    -days 1825 \
    -newkey rsa:2048 \
    -keyout rootCA.key \
    -passout pass:"" \
    -subj "/C=US/ST=CA/L=San Francisco/O=C2PA Python Demo/CN=John Smith" \
    -out rootCA.crt

    echo "Signing the csr with the local cert"
    openssl x509 -req \
    -CA rootCA.crt \
    -CAkey rootCA.key \
    -in kms-signing.csr \
    -out kms-signing.crt \
    -passin pass:"" \
    -days 365 \
    -copy_extensions copyall

    echo "Copying kms-signing.crt to local_volume/kms-signing.crt"
    cat kms-signing.crt rootCA.crt > chain.pem

    echo "Copying chain.pem to local_volume/chain.pem"
    cp chain.pem local_volume/chain.pem

    echo "Adding CERT_CHAIN_PATH to .env.local"
    echo "CERT_CHAIN_PATH=local_volume/chain.pem" >> .env.local

    echo "Adding CLIENT ENV_VARS to .env.local"
    cat <<EOT >> .env.local
CLIENT_ENDPOINT=signer
CLIENT_HOST_PORT=5000
CLIENT_PROTOCOL=http
EOT

    echo "Adding APP ENV_VARS to .env.local"
    cat <<EOT >> .env.local
APP_ENDPOINT=0.0.0.0
APP_HOST_PORT=5000
EOT

    echo "Copying .env.local to local_volume/.env"
    cp .env.local local_volume/.env

    # Copy config of interest in another mapped volume for reference
    cp .env.local config_volume/.env
    cp kms-signing.crt  config_volume/kms-signing.crt
    cp rootCA.crt  config_volume/rootCA.crt
    cp chain.pem config_volume/chain.pem
    
    # Verify the .env file has all required keys
    echo ""
    echo "Verifying .env file has all required keys..."
    MISSING_KEYS=()
    for key in "${REQUIRED_KEYS[@]}"; do
        if ! grep -q "^${key}=" local_volume/.env; then
            MISSING_KEYS+=("$key")
        fi
    done
    
    if [ ${#MISSING_KEYS[@]} -gt 0 ]; then
        echo "ERROR: Setup completed but .env file is missing keys: ${MISSING_KEYS[*]}"
        echo "Contents of .env file:"
        cat local_volume/.env
        exit 1
    else
        echo "✓ All required keys are present in .env file"
        echo ""
        echo "=== Setup completed successfully ==="
        echo "Summary of .env file:"
        echo "  - KMS_KEY_ID: $(grep '^KMS_KEY_ID=' local_volume/.env | cut -d'=' -f2 | head -c 20)..."
        echo "  - CERT_CHAIN_PATH: $(grep '^CERT_CHAIN_PATH=' local_volume/.env | cut -d'=' -f2)"
        echo "  - AWS_ACCESS_KEY_ID: $(grep '^AWS_ACCESS_KEY_ID=' local_volume/.env | cut -d'=' -f2 | head -c 10)..."
        echo "  - AWS_SECRET_ACCESS_KEY: [present]"
    fi
fi

echo "=== local-setup.sh finished ==="
