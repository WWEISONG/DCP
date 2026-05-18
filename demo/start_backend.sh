#!/bin/bash

# Start the Flask backend server
# This script uses the conda environment 'fairimage' which has VINE dependencies

cd "$(dirname "$0")/backend"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "ERROR: conda is not available. Please install conda or activate it first."
    exit 1
fi

# Initialize conda (if not already initialized in this shell)
eval "$(conda shell.bash hook)"

# Activate the fairimage conda environment
echo "Activating conda environment: fairimage"
conda activate fairimage

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate conda environment 'fairimage'."
    echo "Please make sure the environment exists: conda env list"
    exit 1
fi

echo "Using Python from conda environment: $(which python)"
echo "Python version: $(python --version)"

# Install Flask dependencies if needed (minimal dependencies)
if [ ! -f ".fairimage_installed" ]; then
    echo "Installing Flask dependencies in conda environment..."
    pip install -r requirements.txt
    touch .fairimage_installed
    echo "Flask dependencies installed."
else
    echo "Flask dependencies already installed."
fi

# Verify and fix VINE dependencies in conda environment
echo "Checking VINE dependencies in conda environment..."

# Check numpy version and upgrade if needed
NUMPY_VERSION=$(python -c "import numpy; print(numpy.__version__)" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "Current NumPy version: $NUMPY_VERSION"
    # Check if numpy is too old (need >=1.26.0 but <2.0)
    # Simple version check: if version starts with 1.2[0-5] or 1.1 or 1.0, it's too old
    if [[ "$NUMPY_VERSION" =~ ^1\.(0|1|2[0-5])\..*$ ]]; then
        echo "NumPy version $NUMPY_VERSION is too old. Upgrading to 1.26.4..."
        pip install --upgrade --force-reinstall "numpy==1.26.4"
    elif [[ "$NUMPY_VERSION" =~ ^2\. ]]; then
        echo "NumPy version $NUMPY_VERSION is too new (2.x). Downgrading to 1.26.4..."
        pip install --upgrade --force-reinstall "numpy==1.26.4"
    else
        echo "NumPy version $NUMPY_VERSION is compatible."
    fi
else
    echo "NumPy not found. Installing..."
    pip install "numpy==1.26.4"
fi

# Verify VINE dependencies
python -c "import torch; from diffusers import AutoencoderKL" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ VINE dependencies are available in conda environment"
else
    echo "WARNING: VINE dependencies may not be fully available in conda environment."
    echo "The backend will continue, but VINE models may not work."
    echo "Make sure the 'fairimage' conda environment has VINE dependencies installed."
fi

# Set up Python path for VINE models
# Get the demo directory (parent of backend)
DEMO_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
# Get VideoMark directory (parent of demo)
VIDEOMARK_DIR="$(dirname "$DEMO_DIR")"
# Add VINE directory to PYTHONPATH
export PYTHONPATH="${VIDEOMARK_DIR}/VINE:${VIDEOMARK_DIR}:${PYTHONPATH}"

# Start the Flask server with VINE setup
echo "Starting Flask backend server with VINE models setup..."
python setup_vine.py
