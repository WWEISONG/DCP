#!/bin/bash

# Start the React frontend server
# This script installs dependencies and starts the frontend

# Load nvm if it exists
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# If nvm is loaded, use the default Node.js version
if [ -s "$NVM_DIR/nvm.sh" ]; then
    nvm use default 2>/dev/null || nvm use node 2>/dev/null || true
fi

cd "$(dirname "$0")/frontend"

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm is not installed or not in PATH"
    echo ""
    echo "Please install Node.js and npm using one of these methods:"
    echo ""
    echo "Option 1 (Recommended - nvm):"
    echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
    echo "  source ~/.bashrc"
    echo "  nvm install --lts"
    echo "  nvm use --lts"
    echo ""
    echo "Option 2 (System package):"
    echo "  sudo apt update"
    echo "  sudo apt install nodejs npm"
    echo ""
    echo "After installation, run this script again."
    exit 1
fi

# Verify Node.js version (should be 16+)
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 16 ] 2>/dev/null; then
    echo "WARNING: Node.js version is less than 16. React may not work properly."
    echo "Current version: $(node --version)"
    echo "Please upgrade to Node.js 16 or higher."
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Start the React development server
echo "Starting React frontend server..."
npm start
