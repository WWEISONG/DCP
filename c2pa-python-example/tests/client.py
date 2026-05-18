# Copyright 2024 Adobe. All rights reserved.
# This file is licensed to you under the Apache License,
# Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# or the MIT license (http://opensource.org/licenses/MIT),
# at your option.
# Unless required by applicable law or agreed to in writing,
# this software is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR REPRESENTATIONS OF ANY KIND, either express or
# implied. See the LICENSE-MIT and LICENSE-APACHE files for the
# specific language governing permissions and limitations under
# each license.

import argparse
import os
import requests
import json
from c2pa import Builder, Signer, C2paSigningAlg
from PIL import Image
import io
import base64
import mimetypes

from dotenv import dotenv_values

# Example call using default config (signs image-to-sign, puts signed image in out-images folder)
# python tests/client.py ./image-to-sign.jpeg  -o out-images

# Example call using a config env file
# python tests/client.py ./image-to-sign.jpeg  -o out-images -f ./my-example-env-file.env

def get_signer_data_uri(env_file_path=None):
    uri = "http://localhost:5000/signer_data"
    app_config = None

    if env_file_path is not None:
        print(f'Loading environment variables for client from config file {env_file_path}')
        app_config = dotenv_values(env_file_path)
    else:
        env_file_path = os.environ.get('CLIENT_ENV_FILE_PATH')
        if env_file_path is not None:
            print(f'Loading environment variables for client from {env_file_path} file defined in env vars')
            app_config = dotenv_values(env_file_path)

    if app_config is not None:
        host_port = None
        client_endpoint = None
        client_protocol = None

        if 'CLIENT_HOST_PORT' in app_config:
            host_port = app_config['CLIENT_HOST_PORT']
        if 'CLIENT_ENDPOINT' in app_config:
            client_endpoint = app_config['CLIENT_ENDPOINT']
        if 'CLIENT_PROTOCOL' in app_config:
            client_protocol = app_config['CLIENT_PROTOCOL']

        if host_port is not None and client_endpoint is not None and client_protocol is not None:
            uri = f'{client_protocol}://{client_endpoint}:{host_port}/signer_data'
        else:
            raise ValueError(f'Invalid configuration: Cannot build endpoint URL.. Missing one of CLIENT_HOST_PORT, CLIENT_ENDPOINT, CLIENT_PROTOCOL')

    else:
        print(f'No configuration found. Using default URI {uri}')

    return uri

# Generate a sign function from signer data returned by the url
def get_remote_signer(uri: str) -> Signer:
    response = requests.get(uri)

    if response.status_code == 200:
        json_data = response.json()
        print(' Building signer based on response data:')
        print(json_data)
        certs = json_data["cert_chain"]
        # Convert certs string to bytes using UTF-8 encoding
        certs = base64.b64decode(certs.encode("utf-8"))
        alg_str = json_data["alg"].upper()
        try:
            alg = getattr(C2paSigningAlg, alg_str)
            print(f"Using signing algorithm: {alg}")
        except AttributeError:
            raise ValueError(f"Unsupported signing algorithm: {alg_str}")
    else:
        raise ValueError(f"Failed to get signer data: {response.status_code} {response.text}")

    #sign = lambda data: requests.post(json_data["signing_url"], data=data).content
    def remote_sign(data):
        try:
            response = requests.post(json_data["signing_url"], data=data)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error during signing: {e}")
            print(f"Response: {response.text}")
            raise

    # Decode certs to string as expected by Signer.from_callback
    certs_string = certs.decode('utf-8')

    return Signer.from_callback(
        callback=remote_sign,
        alg=alg,
        certs=certs_string,
        tsa_url=json_data["timestamp_url"]
    )

# Generate a thumbnail from a file
def make_thumbnail(file: str) -> io.BytesIO:
    with Image.open(file) as img:
        img.thumbnail((512, 512))
        buffer = io.BytesIO()
        img.save(buffer, "JPEG")
        buffer.seek(0)
        return buffer

# Detect image MIME type from file
def get_image_mime_type(file_path: str) -> str:
    """Detect the MIME type of an image file"""
    # First try to detect from extension
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith('image/'):
        return mime_type
    
    # Fallback: try to detect from PIL
    try:
        with Image.open(file_path) as img:
            format_lower = img.format.lower() if img.format else 'jpeg'
            format_map = {
                'jpeg': 'image/jpeg',
                'jpg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'bmp': 'image/bmp',
                'webp': 'image/webp',
                'tiff': 'image/tiff',
                'tif': 'image/tiff'
            }
            return format_map.get(format_lower, 'image/jpeg')
    except Exception:
        # Default to JPEG if we can't detect
        return 'image/jpeg'


# Example manifest - simplified to match working app.py structure
def create_manifest(author=None, title=None):
    """Create a manifest JSON string. If author/title are provided, add a
    Schema.org CreativeWork assertion so they appear in the verified manifest
    alongside the cert-derived common_name / issuer."""
    assertions = [
        {
            "label": "c2pa.actions",
            "data": {
                "actions": [
                    {
                        "action": "c2pa.created",
                        "softwareAgent": {
                            "name": "C2PA Python Example",
                            "version": "0.2.0"
                        },
                        "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCreation"
                    }
                ]
            }
        }
    ]

    if author or title:
        cw = {
            "@context": "https://schema.org",
            "@type": "CreativeWork",
        }
        if author:
            cw["author"] = [{"@type": "Person", "name": author}]
        if title:
            cw["name"] = title
        assertions.append({
            "label": "stds.schema-org.CreativeWork",
            "data": cw,
        })

    return json.dumps({
        "claim_generator_info": [
            {
                "name": "c2pa test",
                "version": "0.0.1"
            }
        ],
        "assertions": assertions,
    })

# Example of a manifest ingredient
# Note: thumbnail format will be set dynamically based on the actual image format
ingredient_json = {
    "relationship": "parentOf",
    "title": "",
    "thumbnail": {
        "format": "image/jpeg",  # Thumbnails are always JPEG
        "identifier": "thumbnail"
    }
}

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Sign files with C2PA.")
parser.add_argument("files", metavar="F", type=str, nargs="+", help="Files to be signed")
parser.add_argument("-o", "--output", type=str, required=True, help="Output directory")
parser.add_argument("-f", "--envfile", type=str, required=False, help="Config environment file")
parser.add_argument("--author", type=str, default=None,
                    help="Optional author name to embed as a Schema.org CreativeWork assertion")
parser.add_argument("--title", type=str, default=None,
                    help="Optional work title to embed as a Schema.org CreativeWork assertion")

args = parser.parse_args()

# Ensure the output directory exists
os.makedirs(args.output, exist_ok=True)

uri = get_signer_data_uri(args.envfile)
print(f'Uri to get remote signer data {uri}')

signer = get_remote_signer(uri)


# Sign each file and write to the output directory
for file in args.files:
    # Detect the image format first
    image_mime_type = get_image_mime_type(file)
    
    # Create output filename with -signed suffix
    # If we need to convert to JPEG, use .jpg extension
    base_name = os.path.basename(file)
    name_parts = os.path.splitext(base_name)
    
    # Determine the output extension based on actual format
    # C2PA only supports JPEG, so non-JPEG files will be converted
    if image_mime_type == 'image/jpeg':
        output_ext = name_parts[1]  # Keep original extension (.jpg or .jpeg)
    else:
        output_ext = '.jpg'  # Converted files should have .jpg extension
    
    signed_base_name = f"{name_parts[0]}-signed{output_ext}"
    output_file = os.path.join(args.output, signed_base_name)
    print(f"Signing file {file} and saving to {output_file}")

    # Check if output file already exists
    if os.path.exists(output_file):
        print(f"Output file {output_file} already exists, skipping...")
        continue

    try:
        # Detect the image format
        image_mime_type = get_image_mime_type(file)
        print(f"Detected image format: {image_mime_type}")
        
        # C2PA library currently only supports JPEG format
        # Convert non-JPEG images to JPEG for signing
        source_file_path = file
        temp_jpeg_path = None
        needs_conversion = image_mime_type != 'image/jpeg'
        
        if needs_conversion:
            print(f"Converting {image_mime_type} to JPEG for C2PA signing...")
            # Update output file extension to .jpg since we're converting to JPEG
            output_file = os.path.splitext(output_file)[0] + '.jpg'
            print(f"Output file will be saved as: {output_file}")
            # Create temporary JPEG file with a different name to avoid conflicts
            import tempfile
            temp_fd, temp_jpeg_path = tempfile.mkstemp(suffix='.jpg', dir=os.path.dirname(output_file))
            os.close(temp_fd)  # Close the file descriptor, we'll use the path
            
            try:
                with Image.open(file) as img:
                    # Convert RGBA to RGB if necessary (PNG with transparency)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Create white background
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = rgb_img
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    img.save(temp_jpeg_path, 'JPEG', quality=95)
                source_file_path = temp_jpeg_path
                image_mime_type = 'image/jpeg'
                print(f"Converted to JPEG: {temp_jpeg_path}")
            except Exception as e:
                # Clean up temp file on error
                if os.path.exists(temp_jpeg_path):
                    os.remove(temp_jpeg_path)
                raise
        
        # Create manifest for this file
        file_manifest = create_manifest(author=args.author, title=args.title)
        
        with Builder(file_manifest) as builder:
            # Add thumbnail resource (optional, for metadata)
            try:
                builder.add_resource("thumbnail", make_thumbnail(file))
            except Exception as e:
                print(f"Warning: Could not add thumbnail: {e}")

            # Sign the file directly (no ingredient needed for simple signing)
            # Always use JPEG format for signing (C2PA requirement)
            # Verify the source file is actually JPEG before signing
            if needs_conversion:
                # Verify the converted file is valid JPEG
                try:
                    with Image.open(source_file_path) as verify_img:
                        if verify_img.format != 'JPEG':
                            raise ValueError(f"Converted file is not JPEG format, got: {verify_img.format}")
                        print(f"Verified converted file is valid JPEG: {verify_img.size[0]}x{verify_img.size[1]}")
                except Exception as e:
                    print(f"ERROR: Converted file verification failed: {e}")
                    raise
            
            with open(source_file_path, 'rb') as source_file, open(output_file, 'w+b') as dest_file:
                # C2PA library expects MIME type format
                # Try 'image/jpeg' - if that fails, the library might have issues with the file
                try:
                    builder.sign(signer, 'image/jpeg', source_file, dest_file)
                except Exception as sign_error:
                    # If signing fails with "type is unsupported", it might be a file format issue
                    if 'unsupported' in str(sign_error).lower() or 'NotSupported' in str(sign_error):
                        print(f"Signing failed with unsupported type error. Verifying source file...")
                        # Re-read and verify the source file
                        source_file.seek(0)
                        header = source_file.read(4)
                        source_file.seek(0)
                        if header[:2] != b'\xff\xd8':
                            raise ValueError(f"Source file is not a valid JPEG (header: {header.hex()})")
                        print("Source file is valid JPEG. Retrying with explicit format...")
                        # Try again
                        builder.sign(signer, 'image/jpeg', source_file, dest_file)
                    else:
                        raise

            print(f"Signed {file} and saved to {output_file}")
            
            # Clean up temporary JPEG file if we created one
            if needs_conversion and temp_jpeg_path and os.path.exists(temp_jpeg_path):
                try:
                    os.remove(temp_jpeg_path)
                    print(f"Cleaned up temporary file: {temp_jpeg_path}")
                except Exception as e:
                    print(f"Warning: Could not remove temp file {temp_jpeg_path}: {e}")
    except Exception as e:
        print(f"Failed to sign {file}: {e}")
        import traceback
        traceback.print_exc()
