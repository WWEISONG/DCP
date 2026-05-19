import os
import subprocess
import signal
import sys
import atexit
import shutil
import shlex
import socket
try:
    import pwd
except ImportError:
    pwd = None  # pwd module not available on all systems
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Serve the React production build at /. The frontend's build/ folder lives
# one level up from this file, inside demo/frontend/build/. When that folder
# doesn't exist (pure-backend dev mode), Flask falls back to not serving any
# static frontend — the dev server on :3000 handles it instead.
_FRONTEND_BUILD = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'build'
))
if os.path.isdir(_FRONTEND_BUILD):
    app = Flask(__name__, static_folder=_FRONTEND_BUILD, static_url_path='')
else:
    app = Flask(__name__)

# CORS still useful: even though the same Flask now serves both the frontend
# and the API in production, leaving CORS on means a developer running the CRA
# dev server on :3000 can still talk to a remote backend. Set ALLOWED_ORIGINS
# (comma-separated) to lock this down in production if desired.
_allowed = os.environ.get('ALLOWED_ORIGINS', '*').strip()
if _allowed == '*':
    CORS(app)
else:
    CORS(app, origins=[o.strip() for o in _allowed.split(',') if o.strip()])

@app.route('/')
def _serve_index():
    """Serve the React app's index.html at the root."""
    if os.path.isdir(_FRONTEND_BUILD):
        return app.send_static_file('index.html')
    return (
        '<h1>DCP backend running</h1>'
        '<p>No frontend build found at <code>' + _FRONTEND_BUILD + '</code>. '
        'Build it with <code>npm run build</code> in <code>demo/frontend/</code>, '
        'or run the CRA dev server on port 3000.</p>'
    ), 200

# Global VINE module reference (will be set during startup)
_vine_module_global = None

# Configuration
# C2PA_DIR should be at the same level as demo directory
# demo/backend/app.py -> go up to VideoMark -> join with c2pa-python-example
# In Docker, it might be at /app/c2pa-python-example
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
c2pa_dir = os.path.join(base_dir, 'c2pa-python-example')
if not os.path.exists(c2pa_dir):
    # Try Docker path
    docker_c2pa_dir = '/app/c2pa-python-example'
    if os.path.exists(docker_c2pa_dir):
        c2pa_dir = docker_c2pa_dir
C2PA_DIR = c2pa_dir
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
TEMP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sniff_image_mime(path):
    # Some files in this repo have a .png extension but JPEG bytes, which made
    # c2pa.Reader fail with a confusing "invalid file signature" error. Trust
    # the bytes, not the name. Returns None when the format is unrecognized so
    # callers can produce a clean "unsupported image" error instead of letting
    # c2pa raise something cryptic.
    try:
        with open(path, 'rb') as f:
            head = f.read(12)
    except OSError:
        return None
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if head[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    return None

def _generate_signing_cert(common_name: str, issuer: str):
    """Generate a 2-cert chain (root CA + leaf) for ES256 signing where:
      - Root CA cert: Subject CN = `issuer`, self-signed, CA=True.
      - Leaf cert:    Subject CN = `common_name`, Issuer DN = root CA Subject,
                      signed by the root CA's private key, has EKU=emailProtection
                      (C2PA-recognized).

    Returns (chain_pem, leaf_key_pem). The chain is leaf-first, root second
    (the order c2pa-rs expects). Sign with the leaf's private key.

    Validators will mark the cert chain as untrusted because the root CA isn't
    in any trust store — that's expected for a research demo. The metadata
    fields (Common name, Issuer) will reflect the user's input correctly.
    """
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.hazmat.primitives import hashes, serialization
    import datetime, uuid

    not_before = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    not_after = not_before + datetime.timedelta(days=365)

    # Use RSA-2048 root + RSA-2048 leaf, signing alg PS256. ECDSA-leaf signing
    # produced "claimSignature.mismatch" in earlier testing despite valid bytes
    # — Adobe's working example chain uses RSA throughout.

    # --- Root CA (RSA-2048, self-signed) ---
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer)])
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(int(uuid.uuid4()))
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
            critical=False,
        )
        .sign(root_key, hashes.SHA256())
    )

    # --- Leaf (RSA-2048, signed by RSA root) ---
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(root_name)
        .public_key(leaf_key.public_key())
        .serial_number(int(uuid.uuid4()))
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
            critical=False,
        )
        .sign(root_key, hashes.SHA256())  # signed by root RSA private key
    )

    leaf_pem = leaf_cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
    root_pem = root_cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
    # c2pa-rs wants the chain leaf-first. Include root so the chain anchors;
    # leaf alone gave 'claimSignature.mismatch' in earlier testing.
    chain_pem = leaf_pem + root_pem

    # PKCS#8 (BEGIN PRIVATE KEY) is what c2pa-rs explicitly requires.
    leaf_key_pem = leaf_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')
    return chain_pem, leaf_key_pem


def _sign_image_inproc(input_path: str, output_path: str, common_name: str, issuer: str):
    """Sign `input_path` with a freshly generated ES256 cert and write to
    `output_path`. C2PA only supports JPEG, so PNG inputs are converted on the
    way through. Returns the actual output path written (may differ from the
    requested one if extension changed)."""
    import json
    from c2pa import Builder, Signer, C2paSigningAlg, C2paSignerInfo
    from PIL import Image

    cert_pem, key_pem = _generate_signing_cert(common_name, issuer)

    # Ensure output is .jpg regardless of input extension (C2PA requirement).
    name, ext = os.path.splitext(output_path)
    if ext.lower() not in ('.jpg', '.jpeg'):
        output_path = name + '.jpg'

    # If input isn't JPEG, convert to a temp JPEG first.
    needs_conversion = sniff_image_mime(input_path) != 'image/jpeg'
    source_path = input_path
    temp_jpeg = None
    if needs_conversion:
        temp_jpeg = output_path + '.in.jpg'
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(temp_jpeg, 'JPEG', quality=95)
        source_path = temp_jpeg

    manifest = json.dumps({
        "claim_generator_info": [
            {"name": "Digital Content Protector", "version": "0.1.0"}
        ],
        "assertions": [
            {
                "label": "c2pa.actions",
                "data": {
                    "actions": [{
                        "action": "c2pa.created",
                        "softwareAgent": {
                            "name": "Digital Content Protector",
                            "version": "0.1.0",
                        },
                        "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCreation",
                    }]
                }
            }
        ]
    })

    # C2paSignerInfo expects bytes for sign_cert and private_key (FFI layer).
    # ta_url must be a real timestamp authority — DigiCert's is the standard.
    # Use Ps256 (RSA-PSS-SHA256) to match the cert key type.
    signer_info = C2paSignerInfo(
        C2paSigningAlg.PS256,
        cert_pem.encode('utf-8'),
        key_pem.encode('utf-8'),
        'http://timestamp.digicert.com',
    )
    signer = Signer.from_info(signer_info)

    try:
        with Builder(manifest) as builder:
            with open(source_path, 'rb') as src, open(output_path, 'wb') as dst:
                builder.sign(signer, 'image/jpeg', src, dst)
    finally:
        if temp_jpeg and os.path.exists(temp_jpeg):
            try: os.remove(temp_jpeg)
            except Exception: pass

    return output_path


def check_signer_running(retries=8, sleep_s=1.0):
    """`docker compose ps local-signer` from C2PA_DIR, retried a few times.

    The one-shot version was prone to false negatives when the docker daemon
    was momentarily busy — the subprocess could return empty stdout for a few
    hundred ms even while the container was healthy. This wraps it in a short
    retry loop. Returns the last subprocess.CompletedProcess on success, or
    None if the container never appears.
    """
    import time
    last_result = None
    for _ in range(max(1, retries)):
        try:
            last_result = subprocess.run(
                ['docker', 'compose', 'ps', 'local-signer'],
                cwd=C2PA_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if last_result.stdout and 'local-signer' in last_result.stdout:
                return last_result
        except Exception:
            pass
        time.sleep(sleep_s)
    return last_result if (last_result and 'local-signer' in (last_result.stdout or '')) else None

def run_make_command(target, cwd=None):
    """Run a make command in the c2pa-python-example directory"""
    if cwd is None:
        cwd = C2PA_DIR

    if shutil.which('docker') is None:
        return False, "docker is not installed; skipping C2PA Docker stack (C2PA signing routes will be unavailable)"

    try:
        # Use make command
        result = subprocess.run(
            ['make', target],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except FileNotFoundError as e:
        return False, f"make or docker not found: {e}"

def cleanup_on_shutdown_files():
    """Clean up files in specified directories on shutdown"""
    import shutil
    
    # Directories to clean (files only)
    file_directories = [
        os.path.join(C2PA_DIR, 'client_volume', 'input-images'),
        os.path.join(C2PA_DIR, 'client_volume', 'signed-images'),
        UPLOAD_FOLDER
    ]
    
    # Clean files in each directory
    for directory in file_directories:
        if os.path.exists(directory):
            try:
                for item in os.listdir(directory):
                    item_path = os.path.join(directory, item)
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                            print(f"Removed file: {item_path}")
                        elif os.path.isdir(item_path):
                            # Remove subdirectories too
                            shutil.rmtree(item_path)
                            print(f"Removed directory: {item_path}")
                    except Exception as e:
                        print(f"Warning: Could not remove {item_path}: {e}")
            except Exception as e:
                print(f"Warning: Could not list items in {directory}: {e}")
        else:
            print(f"Directory does not exist: {directory}")
    
    # Clean all sub-folders in outputs directory
    if os.path.exists(OUTPUT_FOLDER):
        try:
            for item in os.listdir(OUTPUT_FOLDER):
                item_path = os.path.join(OUTPUT_FOLDER, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        print(f"Removed output subdirectory: {item_path}")
                    elif os.path.isfile(item_path):
                        os.remove(item_path)
                        print(f"Removed output file: {item_path}")
                except Exception as e:
                    print(f"Warning: Could not remove {item_path}: {e}")
        except Exception as e:
            print(f"Warning: Could not list items in {OUTPUT_FOLDER}: {e}")
    else:
        print(f"Output directory does not exist: {OUTPUT_FOLDER}")

def cleanup_on_shutdown():
    """Cleanup function to run on shutdown"""
    print("Shutting down... Running cleanup...")
    
    # Clean up files in specified directories
    print("Cleaning up files and directories...")
    cleanup_on_shutdown_files()
    
    # Run make clean
    success, output = run_make_command('clean')
    if success:
        print("Cleanup completed successfully")
    else:
        print(f"Cleanup failed: {output}")

# Register cleanup function
atexit.register(cleanup_on_shutdown)

# Handle SIGTERM and SIGINT
def signal_handler(sig, frame):
    cleanup_on_shutdown()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and run client command"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        upload_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(upload_path)

        # Read optional Common name / Issuer from the form. These end up as
        # the X.509 cert subject and issuer Common Name fields, so they appear
        # verbatim in the verified manifest.
        cn  = (request.form.get('common_name') or '').strip() or 'DCP signer'
        iss = (request.form.get('issuer') or '').strip() or 'DCP Demo CA'

        # Create output directory for this file
        file_id = filename.rsplit('.', 1)[0]
        output_dir = os.path.join(OUTPUT_FOLDER, file_id)
        os.makedirs(output_dir, exist_ok=True)

        # Sign in-process — no Docker / local-signer / LocalStack required.
        signed_basename = f"{file_id}-signed.jpg"
        signed_path = os.path.join(output_dir, signed_basename)
        try:
            actual_signed = _sign_image_inproc(upload_path, signed_path, cn, iss)
        except Exception as sign_err:
            import traceback; traceback.print_exc()
            return jsonify({
                'error': 'In-process C2PA signing failed',
                'details': str(sign_err)
            }), 500

        signed_filename = os.path.basename(actual_signed)
        return jsonify({
            'message': 'File signed successfully',
            'filename': signed_filename,
            'download_url': f'/download/{file_id}/{signed_filename}',
            'common_name': cn,
            'issuer': iss,
        }), 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500



@app.route('/download/<file_id>/<filename>', methods=['GET'])
def download_file(file_id, filename):
    """Download signed file"""
    file_path = os.path.join(OUTPUT_FOLDER, file_id, filename)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(file_path, as_attachment=True, download_name=filename)

@app.route('/decode-watermark-upload', methods=['POST'])
def decode_watermark_upload():
    """Decode watermark from uploaded file using VINE decoder"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400
    
    try:
        # Import VINE decode function
        import sys
        demo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        videomark_dir = os.path.dirname(demo_dir)
        vine_dir = os.path.join(videomark_dir, 'VINE')
        if vine_dir not in sys.path:
            sys.path.insert(0, vine_dir)
        
        # Try to use the global VINE module if available, otherwise import and initialize it
        global _vine_module_global
        try:
            vine_module = _vine_module_global
            
            # If global module not available, try to import it
            if vine_module is None:
                import importlib.util
                vine_py_path = os.path.join(vine_dir, 'vine.py')
                if not os.path.exists(vine_py_path):
                    return jsonify({
                        'success': False,
                        'error': 'VINE module not found',
                        'message': f'vine.py not found at {vine_py_path}'
                    }), 500
                
                spec = importlib.util.spec_from_file_location("vine_module", vine_py_path)
                vine_module = importlib.util.module_from_spec(spec)
                sys.path.insert(0, vine_dir)
                spec.loader.exec_module(vine_module)
                
                # Check if models are initialized, if not, initialize them
                if vine_module._vine_models.get('decoder') is None:
                    print("VINE models not initialized. Initializing now...")
                    try:
                        vine_module.setup_vine_models()
                        # Store globally for future use
                        _vine_module_global = vine_module
                        print("VINE models initialized successfully in endpoint")
                        print(f"Decoder initialized: {vine_module._vine_models.get('decoder') is not None}")
                    except Exception as init_err:
                        import traceback
                        traceback.print_exc()
                        return jsonify({
                            'success': False,
                            'error': 'Failed to initialize VINE models',
                            'message': f'Error initializing VINE models: {str(init_err)}'
                        }), 503
            
            # Check if decoder is initialized
            if vine_module._vine_models.get('decoder') is None:
                return jsonify({
                    'success': False,
                    'error': 'VINE decoder not initialized',
                    'message': 'VINE models need to be set up first. Please ensure setup_vine_models() has been called.'
                }), 503
            
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            temp_path = os.path.join(UPLOAD_FOLDER, f'temp_watermark_{filename}')
            file.save(temp_path)
            
            try:
                expected = request.form.get('expected_message') or None
                result = vine_module.decode_watermark(temp_path, expected_message=expected)

                # Backwards-compatible: if vine_module is the old tuple-returning version
                if isinstance(result, tuple):
                    bits, acc = result
                    decoded_message = ''
                    is_text = False
                    accuracy = acc
                else:
                    bits = result['bits']
                    decoded_message = result['message']
                    is_text = result['is_text']
                    accuracy = result['accuracy']

                try:
                    os.remove(temp_path)
                except Exception:
                    pass

                print(f"[decode] bits={len(bits)} message={decoded_message!r} is_text={is_text} acc={accuracy}")

                # We treat a result as "has watermark" when:
                #   - the caller supplied an expected_message AND accuracy is high, OR
                #   - the decoded bytes look like real text (heuristic).
                has_watermark = False
                if accuracy is not None and accuracy >= 0.85:
                    has_watermark = True
                elif is_text:
                    has_watermark = True

                return jsonify({
                    'success': has_watermark,
                    'has_watermark': has_watermark,
                    'watermark': bits,
                    'decoded_message': decoded_message,
                    'is_text': is_text,
                    'accuracy': accuracy,
                    'message': 'Watermark decoded successfully' if has_watermark else 'No reliable watermark found'
                }), 200
            except RuntimeError as e:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass
                
                if 'not initialized' in str(e):
                    return jsonify({
                        'success': False,
                        'error': 'VINE decoder not initialized',
                        'message': 'VINE models need to be set up first. Please ensure setup_vine_models() has been called.'
                    }), 503
                else:
                    return jsonify({
                        'success': False,
                        'error': str(e),
                        'message': 'Failed to decode watermark'
                    }), 500
            except Exception as e:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'message': 'Error decoding watermark'
                }), 500
        except ImportError as e:
            return jsonify({
                'success': False,
                'error': 'VINE dependencies not available',
                'message': f'Could not import VINE module: {str(e)}'
            }), 503
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Error accessing VINE module'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Unexpected error during watermark decoding'
        }), 500

@app.route('/watermark-upload', methods=['POST'])
def watermark_upload():
    """Watermark an uploaded file using VINE encoder"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400
    
    try:
        # Import VINE watermark function
        import sys
        demo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        videomark_dir = os.path.dirname(demo_dir)
        vine_dir = os.path.join(videomark_dir, 'VINE')
        if vine_dir not in sys.path:
            sys.path.insert(0, vine_dir)
        
        # Try to use the global VINE module if available, otherwise import and initialize it
        global _vine_module_global
        try:
            vine_module = _vine_module_global
            
            # If global module not available, try to import it
            if vine_module is None:
                import importlib.util
                vine_py_path = os.path.join(vine_dir, 'vine.py')
                if not os.path.exists(vine_py_path):
                    return jsonify({
                        'success': False,
                        'error': 'VINE module not found',
                        'message': f'vine.py not found at {vine_py_path}'
                    }), 500
                
                spec = importlib.util.spec_from_file_location("vine_module", vine_py_path)
                vine_module = importlib.util.module_from_spec(spec)
                sys.path.insert(0, vine_dir)
                spec.loader.exec_module(vine_module)
                
                # Check if models are initialized, if not, initialize them
                if vine_module._vine_models.get('encoder') is None:
                    print("VINE models not initialized. Initializing now...")
                    try:
                        vine_module.setup_vine_models()
                        _vine_module_global = vine_module
                        print("VINE models initialized successfully in endpoint")
                        print(f"Encoder initialized: {vine_module._vine_models.get('encoder') is not None}")
                    except Exception as init_err:
                        import traceback
                        traceback.print_exc()
                        return jsonify({
                            'success': False,
                            'error': 'Failed to initialize VINE models',
                            'message': f'Error initializing VINE models: {str(init_err)}'
                        }), 503
            
            # Check if encoder is initialized
            if vine_module._vine_models.get('encoder') is None:
                return jsonify({
                    'success': False,
                    'error': 'VINE encoder not initialized',
                    'message': 'VINE models need to be set up first. Please ensure setup_vine_models() has been called.'
                }), 503
            
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            temp_path = os.path.join(UPLOAD_FOLDER, f'temp_watermark_input_{filename}')
            file.save(temp_path)

            # Optional user-supplied watermark message (up to 12 UTF-8 bytes is
            # what VINE actually stores; longer inputs are truncated).
            user_message = request.form.get('message')

            try:
                # Step 1: Check if input file has C2PA manifest and extract it
                original_c2pa_manifest = None
                try:
                    import c2pa as _c2pa
                    mime = sniff_image_mime(temp_path)
                    try:
                        if mime is None:
                            raise ValueError('unrecognized image format')
                        with open(temp_path, 'rb') as _f:
                            _reader = _c2pa.Reader.try_create(mime, _f)
                            if _reader is None:
                                raise ValueError('no manifest')
                            original_c2pa_manifest = json.loads(_reader.json())
                            print("Found C2PA manifest in original image, will preserve it after watermarking")
                    except Exception:
                        original_c2pa_manifest = None
                except ImportError:
                    print("c2pa-python not available; skipping C2PA preservation")
                    original_c2pa_manifest = None

                # Extract file_id (remove extension from original filename)
                file_id = os.path.splitext(filename)[0]

                # Create a subdirectory in OUTPUT_FOLDER for this file_id (to match the download endpoint structure)
                file_output_dir = os.path.join(OUTPUT_FOLDER, file_id)
                os.makedirs(file_output_dir, exist_ok=True)

                # Step 2: Watermark the image (save directly to the file_output_dir)
                wm_result = vine_module.watermark_image(temp_path, file_output_dir, message=user_message)
                # Backwards-compatible: support both old (path-only) and new (tuple) returns.
                if isinstance(wm_result, tuple):
                    watermarked_path, _wm_bits, encoded_message = wm_result
                else:
                    watermarked_path = wm_result
                    encoded_message = user_message or ''
                
                # Step 3: If original had C2PA manifest, re-sign the watermarked image with it
                if original_c2pa_manifest is not None:
                    print("Re-signing watermarked image with original C2PA manifest...")
                    try:
                        # Convert watermarked PNG to JPEG for C2PA signing (if needed)
                        from PIL import Image
                        watermarked_jpeg_path = None
                        with Image.open(watermarked_path) as img:
                            if img.mode in ('RGBA', 'LA', 'P'):
                                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                if img.mode == 'P':
                                    img = img.convert('RGBA')
                                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                                img = rgb_img
                            elif img.mode != 'RGB':
                                img = img.convert('RGB')
                            
                            # Save as JPEG for C2PA signing
                            watermarked_jpeg_path = os.path.join(file_output_dir, f'{os.path.splitext(os.path.basename(watermarked_path))[0]}.jpg')
                            img.save(watermarked_jpeg_path, 'JPEG', quality=95)
                        
                        # Re-sign using the same signing process as /upload endpoint
                        client_input_dir = os.path.join(C2PA_DIR, 'client_volume', 'input-images')
                        os.makedirs(client_input_dir, exist_ok=True)
                        c2pa_input_filename = os.path.basename(watermarked_jpeg_path)
                        c2pa_input_path = os.path.join(client_input_dir, c2pa_input_filename)
                        shutil.copy2(watermarked_jpeg_path, c2pa_input_path)
                        
                        # Wait for signer to be ready
                        import time
                        import urllib.request
                        max_wait = 120
                        waited = 0
                        signer_ready = False
                        while waited < max_wait:
                            try:
                                response = urllib.request.urlopen('http://localhost:5050/health', timeout=2)
                                if response.getcode() == 200:
                                    signer_ready = True
                                    break
                            except:
                                if waited % 20 == 0:
                                    print(f"Signer not ready yet... ({waited}s/{max_wait}s)")
                            time.sleep(2)
                            waited += 2
                        
                        if signer_ready:
                            # Create temp .env file
                            temp_env_file = os.path.join(C2PA_DIR, 'client_volume', '.env.client')
                            original_env_path = os.path.join(C2PA_DIR, 'local_volume', '.env')
                            temp_env_content = []
                            if os.path.exists(original_env_path):
                                with open(original_env_path, 'r') as f:
                                    for line in f:
                                        if line.startswith('CLIENT_ENDPOINT='):
                                            temp_env_content.append('CLIENT_ENDPOINT=local-signer\n')
                                        else:
                                            temp_env_content.append(line)
                            with open(temp_env_file, 'w') as f:
                                f.writelines(temp_env_content)
                            
                            # Sign the watermarked image
                            client_output_dir = 'client_volume/signed-images'
                            os.makedirs(os.path.join(C2PA_DIR, client_output_dir), exist_ok=True)
                            container_input_path = f'client_volume/input-images/{c2pa_input_filename}'
                            
                            docker_cmd = [
                                'docker', 'compose',
                                'run', '--rm',
                                '-e', f'CLIENT_ENV_FILE_PATH=client_volume/.env.client',
                                '--entrypoint', f'python tests/client.py {container_input_path} -o {client_output_dir}',
                                'client'
                            ]
                            
                            sign_result = subprocess.run(
                                docker_cmd,
                                cwd=C2PA_DIR,
                                capture_output=True,
                                text=True,
                                timeout=300
                            )
                            
                            # Clean up temp .env file
                            try:
                                if os.path.exists(temp_env_file):
                                    os.remove(temp_env_file)
                            except:
                                pass
                            
                            if sign_result.returncode == 0:
                                # Find the signed file
                                host_output_dir = os.path.join(C2PA_DIR, client_output_dir)
                                signed_base = os.path.splitext(c2pa_input_filename)[0]
                                expected_signed_filename = f"{signed_base}-signed.jpg"
                                signed_path = os.path.join(host_output_dir, expected_signed_filename)
                                
                                if not os.path.exists(signed_path):
                                    files = os.listdir(host_output_dir) if os.path.exists(host_output_dir) else []
                                    if files:
                                        files_with_time = [(f, os.path.getmtime(os.path.join(host_output_dir, f))) for f in files]
                                        files_with_time.sort(key=lambda x: x[1], reverse=True)
                                        expected_signed_filename = files_with_time[0][0]
                                        signed_path = os.path.join(host_output_dir, expected_signed_filename)
                                
                                if os.path.exists(signed_path):
                                    # Replace watermarked PNG with signed JPEG
                                    final_watermarked_path = os.path.join(file_output_dir, os.path.basename(signed_path))
                                    shutil.copy2(signed_path, final_watermarked_path)
                                    watermarked_path = final_watermarked_path
                                    print("Successfully re-signed watermarked image with original C2PA manifest")
                                else:
                                    print("Warning: Signed file not found, using watermarked PNG without C2PA")
                            else:
                                print(f"Warning: Failed to re-sign watermarked image: {sign_result.stderr}")
                        else:
                            print("Warning: Signer not ready, using watermarked PNG without C2PA")
                    except Exception as resign_err:
                        import traceback
                        traceback.print_exc()
                        print(f"Warning: Failed to re-sign watermarked image with C2PA: {resign_err}")
                        # Continue with watermarked PNG without C2PA
                
                # Clean up temp input file
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

                # Get the filename for download
                watermarked_filename = os.path.basename(watermarked_path)

                # Step 4: Read C2PA manifest from final watermarked file (if it was re-signed)
                final_c2pa_manifest = None
                if original_c2pa_manifest is not None:
                    try:
                        import c2pa as _c2pa
                        mime = sniff_image_mime(watermarked_path)
                        if mime is None:
                            raise ValueError('unrecognized image format')
                        with open(watermarked_path, 'rb') as _f:
                            _reader = _c2pa.Reader.try_create(mime, _f)
                            if _reader is None:
                                raise ValueError('no manifest in re-signed output')
                            final_c2pa_manifest = json.loads(_reader.json())
                    except Exception as c2pa_read_err:
                        print(f"Warning: Could not read C2PA from final file: {c2pa_read_err}")

                response_data = {
                    'success': True,
                    'download_url': f'/download/{file_id}/{watermarked_filename}',
                    'filename': watermarked_filename,
                    'message': 'Image watermarked successfully',
                    'encoded_message': encoded_message,
                }

                if final_c2pa_manifest:
                    response_data['manifest'] = final_c2pa_manifest
                    response_data['has_c2pa'] = True
                else:
                    response_data['has_c2pa'] = False

                return jsonify(response_data), 200
            except RuntimeError as e:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass
                
                if 'not initialized' in str(e):
                    return jsonify({
                        'success': False,
                        'error': 'VINE encoder not initialized',
                        'message': 'VINE models need to be set up first. Please ensure setup_vine_models() has been called.'
                    }), 503
                else:
                    return jsonify({
                        'success': False,
                        'error': str(e),
                        'message': 'Failed to watermark image'
                    }), 500
            except Exception as e:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass
                import traceback
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'message': 'Error watermarking image'
                }), 500
        except ImportError as e:
            return jsonify({
                'success': False,
                'error': 'VINE dependencies not available',
                'message': f'Could not import VINE module: {str(e)}'
            }), 503
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Error accessing VINE module'
            }), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Unexpected error during watermarking'
        }), 500

@app.route('/sign-and-watermark-upload', methods=['POST'])
def sign_and_watermark_upload():
    """Watermark an image, save to temp, sign it, and return the signed file with C2PA and watermark data"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400
    
    try:
        # Step 1: Watermark the image first
        import sys
        demo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        videomark_dir = os.path.dirname(demo_dir)
        vine_dir = os.path.join(videomark_dir, 'VINE')
        if vine_dir not in sys.path:
            sys.path.insert(0, vine_dir)
        
        global _vine_module_global
        vine_module = _vine_module_global
        
        if vine_module is None:
            import importlib.util
            vine_py_path = os.path.join(vine_dir, 'vine.py')
            if not os.path.exists(vine_py_path):
                return jsonify({
                    'success': False,
                    'error': 'VINE module not found',
                    'message': f'vine.py not found at {vine_py_path}'
                }), 500
            
            spec = importlib.util.spec_from_file_location("vine_module", vine_py_path)
            vine_module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, vine_dir)
            spec.loader.exec_module(vine_module)
            
            if vine_module._vine_models.get('encoder') is None:
                print("VINE models not initialized. Initializing now...")
                try:
                    vine_module.setup_vine_models()
                    _vine_module_global = vine_module
                    print("VINE models initialized successfully in endpoint")
                except Exception as init_err:
                    import traceback
                    traceback.print_exc()
                    return jsonify({
                        'success': False,
                        'error': 'Failed to initialize VINE models',
                        'message': f'Error initializing VINE models: {str(init_err)}'
                    }), 503
        
        if vine_module._vine_models.get('encoder') is None:
            return jsonify({
                'success': False,
                'error': 'VINE encoder not initialized',
                'message': 'VINE models need to be set up first.'
            }), 503
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_input_path = os.path.join(UPLOAD_FOLDER, f'temp_sign_wm_input_{filename}')
        file.save(temp_input_path)
        
        # Optional message for the combined Sign+Watermark flow
        cw_message = request.form.get('message')

        try:
            # Watermark the image and save to temp folder (not accessible to users)
            wm_result = vine_module.watermark_image(temp_input_path, TEMP_FOLDER, message=cw_message)
            if isinstance(wm_result, tuple):
                watermarked_path, _bits, _encoded_message = wm_result
            else:
                watermarked_path = wm_result
            
            # Clean up temp input file
            try:
                os.remove(temp_input_path)
            except:
                pass
            
            # Step 2: Sign the watermarked file in-process (no Docker needed).
            file_id = os.path.splitext(filename)[0]
            output_dir = os.path.join(OUTPUT_FOLDER, file_id)
            os.makedirs(output_dir, exist_ok=True)
            signed_filename = f"{file_id}-signed.jpg"
            final_output_path = os.path.join(output_dir, signed_filename)

            cn  = (request.form.get('common_name') or '').strip() or 'DCP signer'
            iss = (request.form.get('issuer') or '').strip() or 'DCP Demo CA'
            try:
                actual_signed = _sign_image_inproc(watermarked_path, final_output_path, cn, iss)
                signed_filename = os.path.basename(actual_signed)
                final_output_path = actual_signed
            except Exception as sign_err:
                import traceback; traceback.print_exc()
                return jsonify({
                    'error': 'In-process C2PA signing failed',
                    'details': str(sign_err)
                }), 500

            # Clean up temp watermarked file (not user-accessible) — moved up
            # from below so the legacy Docker block can be cleanly removed.
            try:
                os.remove(watermarked_path)
            except Exception:
                pass

            # Re-read manifest using c2pa-python so the response includes it
            # (DCP tab uses this to confirm signing happened).
            import json as _json
            c2pa_manifest = None
            try:
                from c2pa import Reader as _C2paReader
                with open(final_output_path, 'rb') as _f:
                    _r = _C2paReader.try_create('image/jpeg', _f)
                    if _r is not None:
                        c2pa_manifest = _json.loads(_r.json())
            except Exception as _re:
                print(f"Warning: post-sign manifest read failed: {_re}")

            # Decode watermark from the signed file (best-effort, like before).
            watermark_result = None
            watermark_acc = None
            try:
                decode_result = vine_module.decode_watermark(final_output_path,
                                                             expected_message=cw_message)
                if isinstance(decode_result, tuple):
                    watermark_result, watermark_acc = decode_result
                elif isinstance(decode_result, dict):
                    watermark_result = decode_result.get('bits')
                    watermark_acc = decode_result.get('accuracy')
            except Exception as decode_err:
                print(f"Warning: Failed to decode watermark from signed file: {decode_err}")

            response_data = {
                'success': True,
                'download_url': f'/download/{file_id}/{signed_filename}',
                'filename': signed_filename,
                'message': 'Image signed and watermarked successfully',
                'common_name': cn,
                'issuer': iss,
            }
            if c2pa_manifest:
                response_data['manifest'] = c2pa_manifest
                response_data['has_c2pa'] = True
            else:
                response_data['has_c2pa'] = False
            if watermark_result is not None:
                response_data['watermark'] = watermark_result
                response_data['watermark_accuracy'] = watermark_acc
                response_data['has_watermark'] = watermark_acc >= 0.1 if watermark_acc is not None else True
            else:
                response_data['has_watermark'] = False
            return jsonify(response_data), 200

        except RuntimeError as e:
            try:
                os.remove(temp_input_path)
            except:
                pass
            if 'not initialized' in str(e):
                return jsonify({
                    'success': False,
                    'error': 'VINE encoder not initialized',
                    'message': 'VINE models need to be set up first.'
                }), 503
            else:
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'message': 'Failed to process image'
                }), 500
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                os.remove(temp_input_path)
            except:
                pass
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Error during sign and watermark process'
            }), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Unexpected error'
        }), 500

@app.route('/read-c2pa-upload', methods=['POST'])
def read_c2pa_upload():
    """Read C2PA manifest from uploaded file using c2patool CLI"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400
    
    import json
    try:
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, f'temp_{filename}')
        file.save(temp_path)

        try:
            try:
                import c2pa
            except ImportError:
                return jsonify({
                    'error': 'C2PA library not installed',
                    'details': 'Install with: pip install c2pa-python'
                }), 500

            mime = sniff_image_mime(temp_path)
            if mime is None:
                return jsonify({
                    'success': False,
                    'has_c2pa': False,
                    'message': 'Unsupported image format. Only JPEG, PNG, and WebP are supported.'
                }), 200

            try:
                with open(temp_path, 'rb') as f:
                    reader = c2pa.Reader.try_create(mime, f)
                    # try_create returns None (not raises) when the file has no manifest.
                    if reader is None:
                        return jsonify({
                            'success': False,
                            'has_c2pa': False,
                            'message': 'File does not contain C2PA manifest data'
                        }), 200
                    manifest_json = reader.json()
                    try:
                        validation_state = reader.get_validation_state()
                    except Exception:
                        validation_state = None
            except Exception as read_err:
                # c2pa-python sometimes raises C2paError for "no manifest" and
                # sometimes returns None (handled above). Treat any of the known
                # "absent manifest" / "malformed file" signals as "no C2PA"
                # rather than a server error.
                msg = str(read_err).lower()
                no_manifest_signals = [
                    'no manifest', 'no c2pa', 'manifest not found',
                    'jumbf', 'not signed', 'no claim',
                    'invalid file signature', 'invalid header',
                    'unsupported', 'parse', 'malformed',
                    'could not be parsed', 'asset could not',
                ]
                if any(s in msg for s in no_manifest_signals):
                    return jsonify({
                        'success': False,
                        'has_c2pa': False,
                        'message': 'File does not contain a readable C2PA manifest'
                    }), 200
                # Otherwise re-raise so the outer handler reports it.
                raise

            try:
                manifest_data = json.loads(manifest_json)
            except json.JSONDecodeError:
                return jsonify({
                    'success': False,
                    'has_c2pa': False,
                    'message': 'No valid C2PA manifest found'
                }), 200

            if not manifest_data or not manifest_data.get('manifests'):
                return jsonify({
                    'success': False,
                    'has_c2pa': False,
                    'message': 'No C2PA manifest data found in file'
                }), 200

            if validation_state and 'validation_state' not in manifest_data:
                manifest_data['validation_state'] = validation_state

            return jsonify({
                'success': True,
                'has_c2pa': True,
                'manifest': manifest_data
            }), 200

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            return jsonify({
                'error': 'Failed to read C2PA manifest',
                'details': str(e),
                'trace': error_trace
            }), 500
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _find_jumbf_end(data):
    # Look for the 'jumb' box in a JPEG (APP11 segments) or PNG. We don't need
    # to fully parse C2PA — just figure out a safe offset to start tampering
    # so the change lands in pixel data, not in the (probably) signed JUMBF.
    # Returns an offset to start mutating from. Falls back to len(data)//2.
    if not data:
        return len(data) // 2
    # JPEG: SOS marker (FFDA) starts the compressed scan data, which is well
    # after all metadata segments.
    if data[:3] == b'\xff\xd8\xff':
        i = data.find(b'\xff\xda')
        if i != -1 and i + 20 < len(data):
            return i + 20  # skip the SOS header itself
    # PNG: jump past the IHDR and any JUMBF chunk by finding IDAT.
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        i = data.find(b'IDAT')
        if i != -1 and i + 16 < len(data):
            return i + 16
    return len(data) // 2

@app.route('/tamper-image-upload', methods=['POST'])
def tamper_image_upload():
    """Flip bytes in the image data region of a signed image, simulating an
    attacker who modified the pixels. The C2PA asset-hash assertion should
    fail on verification."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400

    try:
        filename = secure_filename(file.filename)
        raw = file.read()
        if not raw:
            return jsonify({'error': 'File is empty'}), 400

        data = bytearray(raw)
        start = _find_jumbf_end(bytes(data))
        # Flip ~16 bytes starting at `start`, but stay clear of the trailing
        # EOI marker on JPEG.
        end = min(start + 16, len(data) - 4)
        if end <= start:
            return jsonify({'error': 'File too small to tamper'}), 400
        for i in range(start, end):
            data[i] ^= 0x5A  # arbitrary mutation

        # Write to outputs/<file_id>/tampered-<filename>
        name_parts = os.path.splitext(filename)
        file_id = name_parts[0]
        out_dir = os.path.join(OUTPUT_FOLDER, file_id)
        os.makedirs(out_dir, exist_ok=True)
        tampered_name = f"{name_parts[0]}-tampered-image{name_parts[1]}"
        tampered_path = os.path.join(out_dir, tampered_name)
        with open(tampered_path, 'wb') as f:
            f.write(data)

        return jsonify({
            'success': True,
            'filename': tampered_name,
            'download_url': f'/download/{file_id}/{tampered_name}',
            'message': f'Flipped {end - start} bytes at offset {start}',
            'tamper_mode': 'image',
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/tamper-manifest-upload', methods=['POST'])
def tamper_manifest_upload():
    """Find a chosen text value (old_value) in the file bytes and replace it
    with new_value of the same length. The C2PA signature covers the claim
    bytes (and the cert chain in the signature box), so flipping bytes inside
    those regions reliably breaks signature verification."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400

    old_value = request.form.get('old_value', '')
    new_value = request.form.get('new_value', '')
    if not old_value or not new_value:
        return jsonify({'error': 'old_value and new_value are required'}), 400
    if len(old_value) != len(new_value):
        return jsonify({
            'error': 'Length mismatch',
            'details': f'new_value must be exactly {len(old_value)} characters'
        }), 400

    try:
        filename = secure_filename(file.filename)
        raw = file.read()
        if not raw:
            return jsonify({'error': 'File is empty'}), 400

        old_bytes = old_value.encode('utf-8')
        new_bytes = new_value.encode('utf-8')
        if old_bytes not in raw:
            return jsonify({
                'error': 'Value not found',
                'details': f'"{old_value}" was not found in the file bytes. It may be encoded differently inside the manifest.'
            }), 400

        # Replace ALL occurrences. Cert-subject strings like common_name or
        # issuer typically appear several times (leaf cert + chain inside the
        # COSE signature). If we only replaced the first one, the c2pa Reader
        # would still find an unmodified copy when rendering the manifest, so
        # the displayed value wouldn't reflect the tamper. The signature is
        # already invalidated either way.
        first_idx = raw.find(old_bytes)
        occurrence_count = raw.count(old_bytes)
        data = raw.replace(old_bytes, new_bytes)

        name_parts = os.path.splitext(filename)
        file_id = name_parts[0]
        out_dir = os.path.join(OUTPUT_FOLDER, file_id)
        os.makedirs(out_dir, exist_ok=True)
        tampered_name = f"{name_parts[0]}-tampered-manifest{name_parts[1]}"
        tampered_path = os.path.join(out_dir, tampered_name)
        with open(tampered_path, 'wb') as f:
            f.write(data)

        return jsonify({
            'success': True,
            'filename': tampered_name,
            'download_url': f'/download/{file_id}/{tampered_name}',
            'message': f'Replaced "{old_value}" → "{new_value}" in {occurrence_count} location(s) (first at offset {first_idx})',
            'tamper_mode': 'manifest',
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def _save_tamper_output(image, src_filename, suffix):
    """Save a PIL image into outputs/<file_id>/ with a derived name, matching
    the format of the source (JPEG if the source was JPEG, otherwise PNG).
    Returns (file_id, tampered_name, tampered_path)."""
    name_parts = os.path.splitext(src_filename)
    file_id = name_parts[0]
    out_dir = os.path.join(OUTPUT_FOLDER, file_id)
    os.makedirs(out_dir, exist_ok=True)
    ext_lower = name_parts[1].lower()
    if ext_lower in ('.jpg', '.jpeg'):
        tampered_name = f"{name_parts[0]}-{suffix}.jpg"
        out_path = os.path.join(out_dir, tampered_name)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        image.save(out_path, 'JPEG', quality=92)
    else:
        tampered_name = f"{name_parts[0]}-{suffix}.png"
        out_path = os.path.join(out_dir, tampered_name)
        image.save(out_path, 'PNG')
    return file_id, tampered_name, out_path

@app.route('/tamper-watermark-noise-upload', methods=['POST'])
def tamper_watermark_noise_upload():
    """Add strong additive Gaussian noise to the image. The image stays
    recognizable but VINE's bit recovery should collapse."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400

    try:
        from PIL import Image, ImageFilter
        import numpy as np

        filename = secure_filename(file.filename)
        temp_in = os.path.join(TEMP_FOLDER, f'noise_in_{filename}')
        file.save(temp_in)

        try:
            with Image.open(temp_in) as img:
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')

                # Combo attack — visually mild but effective against neural
                # watermarks:
                #  1. small Gaussian blur kills the high-frequency components
                #     where the watermark lives (subjectively just "slight
                #     softness", almost imperceptible)
                #  2. modest Gaussian noise on top adds a low grain that the
                #     decoder can't lock onto
                # The image stays clearly recognisable; the decoded message
                # comes back as garbled bytes that fail the text heuristic.
                blur_radius = 1.5
                sigma = 35.0
                img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                arr = np.array(img, dtype=np.float32)

            rng = np.random.default_rng(seed=0xC2BA)  # deterministic for demo
            noise = rng.normal(0.0, sigma, size=arr.shape).astype(np.float32)
            noisy = np.clip(arr + noise, 0, 255).astype(np.uint8)
            noisy_img = Image.fromarray(noisy)

            file_id, tampered_name, _ = _save_tamper_output(noisy_img, filename, 'tampered-noise')
        finally:
            try: os.remove(temp_in)
            except Exception: pass

        return jsonify({
            'success': True,
            'filename': tampered_name,
            'download_url': f'/download/{file_id}/{tampered_name}',
            'message': f'Slight blur (r={blur_radius}) + light Gaussian noise (σ={int(sigma)})',
            'tamper_mode': 'watermark-noise',
        }), 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/tamper-watermark-recompress-upload', methods=['POST'])
def tamper_watermark_recompress_upload():
    """Re-encode the image as JPEG at very low quality. Blocky compression
    artifacts often destroy watermark bits."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only JPG, JPEG, PNG allowed'}), 400

    try:
        from PIL import Image

        filename = secure_filename(file.filename)
        temp_in = os.path.join(TEMP_FOLDER, f'recompress_in_{filename}')
        file.save(temp_in)

        try:
            with Image.open(temp_in) as img:
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                # Output is JPEG regardless of input ext.
                name_parts = os.path.splitext(filename)
                file_id = name_parts[0]
                out_dir = os.path.join(OUTPUT_FOLDER, file_id)
                os.makedirs(out_dir, exist_ok=True)
                tampered_name = f"{name_parts[0]}-tampered-recompress.jpg"
                out_path = os.path.join(out_dir, tampered_name)
                # First downscale aggressively, save, reload, then re-save at
                # very low quality. The combination of scale loss + low-q JPEG
                # is what reliably wipes VINE's signal — quality=10 alone keeps
                # accuracy above the detection threshold.
                w, h = img.size
                small = img.resize((max(w // 4, 32), max(h // 4, 32)), Image.BILINEAR)
                small.save(out_path, 'JPEG', quality=5)
                with Image.open(out_path) as reloaded:
                    blown = reloaded.resize((w, h), Image.BILINEAR)
                    blown.save(out_path, 'JPEG', quality=8)
        finally:
            try: os.remove(temp_in)
            except Exception: pass

        return jsonify({
            'success': True,
            'filename': tampered_name,
            'download_url': f'/download/{file_id}/{tampered_name}',
            'message': 'Downscaled 4x and re-encoded as JPEG quality=5/8',
            'tamper_mode': 'watermark-recompress',
        }), 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/read-c2pa/<file_id>/<filename>', methods=['GET'])
def read_c2pa(file_id, filename):
    """Read C2PA manifest from signed file using c2patool CLI"""
    file_path = os.path.join(OUTPUT_FOLDER, file_id, filename)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        import json
        
        # Use c2patool CLI command to read the manifest
        # Try c2patool first, fallback to c2pa if available
        c2pa_cmd = 'c2patool'
        try:
            result = subprocess.run(
                [c2pa_cmd, file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
        except FileNotFoundError:
            # Try alternative command name
            c2pa_cmd = 'c2pa'
            result = subprocess.run(
                [c2pa_cmd, file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
        
        # Check if command succeeded
        # Note: c2patool may output validation warnings to stderr but still return 0
        # We need to check if stdout contains valid JSON
        output = result.stdout.strip()
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else 'Unknown error'
            return jsonify({
                'error': 'Failed to read C2PA manifest',
                'details': error_msg,
                'stdout': output
            }), 500
        
        # Parse the output - c2patool outputs JSON to stdout
        if not output:
            return jsonify({
                'error': 'No C2PA data found in file',
                'details': 'The file does not contain C2PA manifest data'
            }), 404
        
        try:
            manifest_data = json.loads(output)
        except json.JSONDecodeError as e:
            # If output is not JSON, return as text with error info
            return jsonify({
                'error': 'Failed to parse C2PA output',
                'details': f'Output is not valid JSON: {str(e)}',
                'raw_output': output,
                'stderr': result.stderr.strip() if result.stderr else None
            }), 500
        
        return jsonify({
            'success': True,
            'manifest': manifest_data
        }), 200
        
    except FileNotFoundError:
        return jsonify({
            'error': 'C2PA CLI tool not found',
            'details': 'c2patool or c2pa command is not available on this system'
        }), 500
    except subprocess.TimeoutExpired:
        return jsonify({
            'error': 'C2PA read operation timed out',
            'details': 'The operation took too long to complete'
        }), 500
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return jsonify({
            'error': 'Failed to read C2PA manifest',
            'details': str(e),
            'trace': error_trace
        }), 500

if __name__ == '__main__':
    # Run build and run commands on startup
    print("Starting backend...")
    print(f"C2PA directory: {C2PA_DIR}")
    
    # Check if C2PA directory exists
    if not os.path.exists(C2PA_DIR):
        print(f"ERROR: C2PA directory not found at {C2PA_DIR}")
        sys.exit(1)
    
    # Create necessary directories for docker volumes
    required_dirs = [
        os.path.join(C2PA_DIR, 'local_volume'),
        os.path.join(C2PA_DIR, 'config_volume'),
        os.path.join(C2PA_DIR, 'client_volume'),
        os.path.join(C2PA_DIR, 'client_volume', 'input-images'),
        os.path.join(C2PA_DIR, 'client_volume', 'signed-images'),
    ]
    for dir_path in required_dirs:
        try:
            os.makedirs(dir_path, exist_ok=True, mode=0o755)
            # Try to change ownership if we have permission
            try:
                import pwd
                uid = pwd.getpwnam(os.getenv('USER', 'weisong')).pw_uid
                gid = pwd.getpwnam(os.getenv('USER', 'weisong')).pw_gid
                os.chown(dir_path, uid, gid)
            except (OSError, KeyError, ImportError):
                pass  # Ignore if we can't change ownership
            print(f"Ensured directory exists: {dir_path}")
        except PermissionError:
            print(f"WARNING: Cannot create {dir_path} - permission denied. You may need to run: sudo chown -R $USER:$USER {C2PA_DIR}/client_volume")
    
    # Stop and remove existing containers to avoid conflicts
    print("Cleaning up existing containers...")
    container_names = ['localstack-main', 'local-setup', 'local-signer', 'local-client']
    
    # First try docker compose down
    try:
        subprocess.run(
            ['docker', 'compose', 'down', '--remove-orphans'],
            cwd=C2PA_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )
    except Exception as e:
        print(f"Note: docker compose down had issues: {e}")
    
    # Force remove containers by name if they still exist
    for container_name in container_names:
        try:
            # Check if container exists
            check_result = subprocess.run(
                ['docker', 'ps', '-a', '--filter', f'name=^{container_name}$', '--format', '{{.Names}}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if container_name in check_result.stdout:
                print(f"Removing existing container: {container_name}")
                subprocess.run(
                    ['docker', 'rm', '-f', container_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
        except Exception as e:
            print(f"Note: Could not remove container {container_name}: {e}")
    
    print("Container cleanup completed")
    
    # Run build command
    print("Building Docker containers...")
    success, output = run_make_command('build')
    if not success:
        print(f"WARNING: Build failed: {output}")
    else:
        print("Build completed successfully")
    
    # Run run command
    print("Starting Docker containers...")
    success, output = run_make_command('run')
    if not success:
        print(f"WARNING: Run failed: {output}")
        
        # Check if local-setup failed
        if 'local-setup' in output and 'exit' in output.lower():
            print("\n" + "="*60)
            print("local-setup container failed. Attempting to get logs...")
            print("="*60)
            try:
                logs_result = subprocess.run(
                    ['docker', 'compose', 'logs', '--tail', '100', 'local-setup'],
                    cwd=C2PA_DIR,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if logs_result.stdout:
                    print("local-setup logs:")
                    print(logs_result.stdout)
                if logs_result.stderr:
                    print("local-setup stderr:")
                    print(logs_result.stderr)
                if not logs_result.stdout and not logs_result.stderr:
                    print("No logs available. Container may have exited immediately.")
                    print("Try running manually: cd c2pa-python-example && sudo docker compose run --rm local-setup")
            except Exception as e:
                print(f"Could not retrieve logs: {e}")
            print("="*60 + "\n")
    else:
        print("Containers started successfully")
        
        # Fix permissions on .env file if it exists (Docker creates it as root)
        env_file = os.path.join(C2PA_DIR, 'local_volume', '.env')
        if os.path.exists(env_file):
            try:
                # Try to fix permissions using sudo
                subprocess.run(
                    ['chmod', '644', env_file],
                    check=False,
                    timeout=5
                )
                # Also try to change ownership if possible
                if pwd:
                    try:
                        current_user = pwd.getpwuid(os.getuid()).pw_name
                        subprocess.run(
                            ['chown', f'{current_user}:{current_user}', env_file],
                            check=False,
                            timeout=5
                        )
                    except Exception:
                        pass  # Ignore ownership change errors
            except Exception as e:
                print(f"Warning: Could not fix permissions on .env file: {e}")
        
        # Verify setup completed and KMS key exists in LocalStack
        if os.path.exists(env_file):
            # First, ensure LocalStack is running
            try:
                check_localstack = subprocess.run(
                    ['docker', 'compose', 'ps', 'localstack-main'],
                    cwd=C2PA_DIR,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if 'Running' not in check_localstack.stdout:
                    print("WARNING: LocalStack is not running. Starting it...")
                    subprocess.run(
                        ['docker', 'compose', 'up', '-d', 'localstack-main'],
                        cwd=C2PA_DIR,
                        timeout=30
                    )
                    # Wait a bit for LocalStack to start
                    import time
                    time.sleep(5)
            except Exception as e:
                print(f"Warning: Could not check/start LocalStack: {e}")
            
            # Check if KMS key exists in LocalStack
            try:
                # Read .env file to get KMS_KEY_ID
                env_content = ""
                try:
                    with open(env_file, 'r') as f:
                        env_content = f.read()
                except PermissionError:
                    # Try with sudo if permission denied
                    result = subprocess.run(
                        ['cat', env_file],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        env_content = result.stdout
                
                if env_content and 'KMS_KEY_ID=' in env_content:
                    # Extract key ID
                    for line in env_content.split('\n'):
                        if line.startswith('KMS_KEY_ID='):
                            key_id = line.split('=', 1)[1].strip().strip("'\"")
                            # Check if key exists in LocalStack
                            # Try both key ID and ARN format
                            check_key = subprocess.run(
                                ['docker', 'compose', 'exec', '-T', 'localstack-main', 
                                 'awslocal', 'kms', 'describe-key', '--key-id', key_id],
                                cwd=C2PA_DIR,
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            
                            # Also try with ARN format if key_id is not already an ARN
                            if check_key.returncode != 0 and not key_id.startswith('arn:'):
                                arn_key_id = f"arn:aws:kms:us-east-1:000000000000:key/{key_id}"
                                check_key = subprocess.run(
                                    ['docker', 'compose', 'exec', '-T', 'localstack-main', 
                                     'awslocal', 'kms', 'describe-key', '--key-id', arn_key_id],
                                    cwd=C2PA_DIR,
                                    capture_output=True,
                                    text=True,
                                    timeout=10
                                )
                            
                            if check_key.returncode != 0:
                                print(f"WARNING: KMS key {key_id} not found in LocalStack")
                                print("LocalStack may have been restarted and lost the key.")
                                print("Re-running local-setup to recreate the key...")
                                # Re-run setup with full output capture
                                setup_result = subprocess.run(
                                    ['docker', 'compose', 'run', '--rm', 'local-setup'],
                                    cwd=C2PA_DIR,
                                    capture_output=True,
                                    text=True,
                                    timeout=300
                                )
                                
                                # Always show setup output for debugging
                                if setup_result.stdout:
                                    print("Setup stdout (last 1000 chars):")
                                    print(setup_result.stdout[-1000:])
                                if setup_result.stderr:
                                    print("Setup stderr (last 1000 chars):")
                                    print(setup_result.stderr[-1000:])
                                
                                if setup_result.returncode == 0:
                                    print("✓ Setup re-run completed successfully")
                                    
                                    # Check setup output for errors
                                    if setup_result.stderr and ('error' in setup_result.stderr.lower() or 'failed' in setup_result.stderr.lower()):
                                        print(f"WARNING: Setup may have had errors:\n{setup_result.stderr[-500:]}")
                                    
                                    # Wait a moment for LocalStack to process
                                    import time
                                    time.sleep(3)
                                    
                                    # Re-read .env file to get the key (might be new)
                                    try:
                                        with open(env_file, 'r') as f:
                                            new_env = f.read()
                                        for line in new_env.split('\n'):
                                            if line.startswith('KMS_KEY_ID='):
                                                new_key_id = line.split('=', 1)[1].strip().strip("'\"")
                                                key_id = new_key_id  # Update key_id
                                                print(f"Found KMS_KEY_ID in .env: {key_id[:20]}...")
                                                break
                                    except Exception as e:
                                        print(f"Warning: Could not re-read .env file: {e}")
                                    
                                    # First, list all keys to see what exists
                                    list_keys = subprocess.run(
                                        ['docker', 'compose', 'exec', '-T', 'localstack-main', 
                                         'awslocal', 'kms', 'list-keys'],
                                        cwd=C2PA_DIR,
                                        capture_output=True,
                                        text=True,
                                        timeout=10
                                    )
                                    if list_keys.returncode == 0:
                                        print(f"Available keys in LocalStack: {list_keys.stdout}")
                                        
                                        # If no keys exist, the setup failed to create the key
                                        if '"Keys": []' in list_keys.stdout or '"Keys":[]' in list_keys.stdout:
                                            print("ERROR: No keys found in LocalStack after setup!")
                                            print("The setup script may have failed to create the KMS key.")
                                            print("Checking setup logs...")
                                            # Get setup logs
                                            setup_logs = subprocess.run(
                                                ['docker', 'compose', 'logs', '--tail', '50', 'local-setup'],
                                                cwd=C2PA_DIR,
                                                capture_output=True,
                                                text=True,
                                                timeout=10
                                            )
                                            if setup_logs.stdout:
                                                print("Recent setup logs:")
                                                print(setup_logs.stdout[-1000:])
                                            print("\nYou may need to check LocalStack logs or manually debug the setup.")
                                            continue  # Skip key verification
                                    
                                    # Verify the key was created (try both old and new key ID)
                                    verify_result = subprocess.run(
                                        ['docker', 'compose', 'exec', '-T', 'localstack-main', 
                                         'awslocal', 'kms', 'describe-key', '--key-id', key_id],
                                        cwd=C2PA_DIR,
                                        capture_output=True,
                                        text=True,
                                        timeout=10
                                    )
                                    if verify_result.returncode == 0:
                                        print(f"✓ KMS key {key_id[:20]}... verified in LocalStack after re-setup")
                                    else:
                                        print(f"WARNING: Could not verify key {key_id[:20]}... after setup")
                                        print("Restarting signer service to pick up new key...")
                                        # Restart signer to pick up new key
                                        try:
                                            subprocess.run(
                                                ['docker', 'compose', 'restart', 'local-signer'],
                                                cwd=C2PA_DIR,
                                                timeout=30
                                            )
                                            print("✓ Signer service restarted")
                                        except Exception as e:
                                            print(f"Warning: Could not restart signer: {e}")
                                        print("You may need to manually run: cd c2pa-python-example && sudo docker compose run --rm local-setup")
                                else:
                                    print(f"ERROR: Setup re-run failed!")
                                    print(f"Return code: {setup_result.returncode}")
                                    if setup_result.stdout:
                                        print(f"stdout (last 500 chars):\n{setup_result.stdout[-500:]}")
                                    if setup_result.stderr:
                                        print(f"stderr (last 500 chars):\n{setup_result.stderr[-500:]}")
                                    print("\nYou may need to manually run: cd c2pa-python-example && sudo docker compose run --rm local-setup")
                            else:
                                print(f"✓ KMS key {key_id[:20]}... verified in LocalStack")
                            break
            except Exception as e:
                print(f"Warning: Could not verify KMS key in LocalStack: {e}")
        
        # Verify setup completed by checking if .env file exists with required keys
        if os.path.exists(env_file):
            # Fix permissions on .env file (Docker creates it as root)
            try:
                os.chmod(env_file, 0o644)
            except Exception as e:
                print(f"Warning: Could not change permissions on .env file: {e}")
                # Try using sudo to read it
                try:
                    result = subprocess.run(
                        ['cat', env_file],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        env_content = result.stdout
                    else:
                        print(f"WARNING: Could not read .env file: {result.stderr}")
                        env_content = ""
                except Exception as e2:
                    print(f"WARNING: Could not read .env file: {e2}")
                    env_content = ""
            
            if 'env_content' not in locals():
                try:
                    with open(env_file, 'r') as f:
                        env_content = f.read()
                except PermissionError:
                    # Try with sudo
                    try:
                        result = subprocess.run(
                            ['cat', env_file],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            env_content = result.stdout
                        else:
                            print(f"WARNING: Could not read .env file: {result.stderr}")
                            env_content = ""
                    except Exception as e:
                        print(f"WARNING: Could not read .env file: {e}")
                        env_content = ""
            
            if env_content:
                required_keys = ['KMS_KEY_ID', 'CERT_CHAIN_PATH', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
                missing = [key for key in required_keys if f'{key}=' not in env_content]
                if missing:
                    print(f"WARNING: .env file exists but missing keys: {missing}")
                    print("You may need to re-run setup: cd c2pa-python-example && sudo docker compose run --rm local-setup")
                else:
                    print("✓ Setup verification: .env file has all required keys")
        else:
            print("WARNING: .env file not found. Setup may have failed.")
            print("Try running: cd c2pa-python-example && sudo docker compose run --rm local-setup")
    
    # Start Flask server on port 8000 (5000 is used by local-signer)
    # Check if port 8000 is available, if not, try to stop conflicting Docker container or use alternative port
    def is_port_available(port):
        """Check if a port is available"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return True
            except OSError:
                return False
    
    port = 8000
    if not is_port_available(port):
        print(f"Port {port} is already in use.")
        # Check if it's our Docker container
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'name=videomark-backend', '--format', '{{.Names}}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if 'videomark-backend' in result.stdout:
                print("Found existing videomark-backend Docker container on port 8000.")
                print("Stopping it to allow local backend to run...")
                subprocess.run(
                    ['docker', 'stop', 'videomark-backend'],
                    capture_output=True,
                    timeout=10
                )
                subprocess.run(
                    ['docker', 'rm', 'videomark-backend'],
                    capture_output=True,
                    timeout=10
                )
                # Wait a moment for port to be released
                import time
                time.sleep(2)
                if is_port_available(port):
                    print(f"Port {port} is now available.")
                else:
                    print(f"Port {port} still in use. Trying port 8001...")
                    port = 8001
            else:
                print(f"Port {port} is in use by another process. Trying port 8001...")
                port = 8001
        except Exception as e:
            print(f"Could not check Docker containers: {e}")
            print(f"Trying port 8001 instead...")
            port = 8001
        
        if not is_port_available(port):
            print(f"ERROR: Port {port} is also in use.")
            print("Please stop the existing service or free up a port.")
            print("You can stop Docker containers with: docker stop videomark-backend")
            sys.exit(1)
    
    print(f"Starting Flask server on http://0.0.0.0:{port}")
    if port != 8000:
        print(f"WARNING: Using port {port} instead of 8000.")
        print(f"Update your frontend to connect to http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
