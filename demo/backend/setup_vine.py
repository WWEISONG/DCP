#!/usr/bin/env python3
"""
Initialize VINE models before starting the Flask server.
This script sets up the VINE models and then imports and starts the Flask app.
"""

import os
import sys

# Add VINE directory to Python path
# Get the demo directory (parent of backend)
demo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Get VideoMark directory (parent of demo)
videomark_dir = os.path.dirname(demo_dir)
# Add VINE directory to path (this allows 'vine' package to be imported)
# In Docker, VINE might be at /app/VINE, so check both locations
vine_dir = os.path.join(videomark_dir, 'VINE')
if not os.path.exists(vine_dir):
    # Try Docker path
    docker_vine_dir = '/app/VINE'
    if os.path.exists(docker_vine_dir):
        vine_dir = docker_vine_dir
if vine_dir not in sys.path:
    sys.path.insert(0, vine_dir)

# First check if torch is available
try:
    import torch
    torch_available = True
except ImportError:
    torch_available = False
    print("=" * 60)
    print("WARNING: PyTorch is not available in this environment.")
    print("VINE models require PyTorch and other dependencies.")
    print("=" * 60)
    print("To use VINE models, please either:")
    print("1. Install VINE dependencies: pip install torch torchvision accelerate transformers")
    print("2. Use a conda environment with VINE already set up")
    print("=" * 60)
    print("Continuing without VINE models...")
    print("=" * 60)

if torch_available:
    try:
        print("=" * 60)
        print("Setting up VINE models...")
        print("=" * 60)
        
        # Import vine.py module (it's a file, not a package)
        import importlib.util
        vine_py_path = os.path.join(vine_dir, 'vine.py')
        if os.path.exists(vine_py_path):
            spec = importlib.util.spec_from_file_location("vine_module", vine_py_path)
            vine_module = importlib.util.module_from_spec(spec)
            # Add vine_dir to sys.path so 'vine' package imports work
            sys.path.insert(0, vine_dir)
            spec.loader.exec_module(vine_module)
            # Call setup_vine_models
            vine_module.setup_vine_models()
            # Store the module globally so app.py can access it
            import app as app_module
            app_module._vine_module_global = vine_module
            print("=" * 60)
            print("VINE models setup completed successfully!")
            print("=" * 60)
        else:
            print(f"WARNING: vine.py not found at {vine_py_path}")
            print("VINE models will not be available. Continuing without VINE...")
        
    except ImportError as e:
        print(f"WARNING: Could not import VINE setup function: {e}")
        print("VINE models will not be available. Continuing without VINE...")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"WARNING: Error setting up VINE models: {e}")
        print("VINE models will not be available. Continuing without VINE...")
        import traceback
        traceback.print_exc()

# Now import and run the Flask app
if __name__ == '__main__':
    # Change to backend directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    
    # Import app module - this will load the Flask app but won't run the if __name__ block
    # since __name__ will be 'app' when imported, not '__main__'
    import app as app_module
    
    # Now we need to execute the startup code that's in app.py's if __name__ == '__main__' block
    # We'll do this by executing app.py with __name__ set to '__main__'
    # But actually, simpler: just run app.py as a script using runpy
    import runpy
    runpy.run_path('app.py', run_name='__main__')
