import os, gc, torch
from vine.src.vine_turbo import VINE_Turbo
from accelerate.utils import set_seed
from vine.src.stega_encoder_decoder import CustomConvNeXt
from PIL import Image
from torchvision import transforms
import numpy as np
import time
import json


# VINE-B-Enc/Dec embed/recover a 100-bit payload.
# We use the first 96 bits (12 bytes UTF-8) for a message; the last 4 bits
# are padding.
MESSAGE_BYTES = 12
PAYLOAD_BITS = 100


def _default_device():
    if torch.cuda.is_available():
        return torch.device('cuda')
    if getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
        return torch.device('mps')
    return torch.device('cpu')


def _empty_cache():
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


_vine_models = {
    'encoder': None,
    'decoder': None,
}


def message_to_bits(message):
    """Encode a UTF-8 string into the 104-bit VINE payload (12 bytes + 8 pad)."""
    if message is None:
        message = ''
    # Truncate / pad to exactly MESSAGE_BYTES bytes of UTF-8.
    raw = message.encode('utf-8')[:MESSAGE_BYTES]
    raw = raw + b' ' * (MESSAGE_BYTES - len(raw))
    bits = []
    for byte in raw:
        bits.extend(int(b) for b in format(byte, '08b'))
    # Pad to PAYLOAD_BITS
    bits.extend([0] * (PAYLOAD_BITS - len(bits)))
    return bits


def bits_to_message(bits):
    """Decode the first 12 bytes of the payload as a UTF-8 string, tolerating
    bit errors. Returns (decoded_str, is_likely_text). `is_likely_text` is True
    when the decoded bytes are valid UTF-8 and mostly printable — a quick
    heuristic for distinguishing real watermark output from random noise."""
    bit_str = ''.join(str(int(b)) for b in bits[:MESSAGE_BYTES * 8])
    bytes_out = bytearray()
    for i in range(0, len(bit_str), 8):
        bytes_out.append(int(bit_str[i:i + 8], 2))
    try:
        decoded = bytes_out.decode('utf-8').rstrip('\x00').rstrip()
        printable = sum(1 for c in decoded if c.isprintable())
        is_text = len(decoded) > 0 and printable / max(len(decoded), 1) >= 0.7
        return decoded, is_text
    except UnicodeDecodeError:
        return bytes_out.hex(), False


def setup_vine_models():
    """Load VINE encoder + decoder. No message is pre-encoded; callers pass
    a message string to `watermark_image` at request time."""
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'
    device = _default_device()
    print(f'[vine] Using device: {device}')
    set_seed(42)

    watermark_encoder = VINE_Turbo.from_pretrained('Shilin-LU/VINE-B-Enc', device=str(device))
    watermark_encoder.to(device)

    decoder = CustomConvNeXt.from_pretrained('Shilin-LU/VINE-B-Dec')
    decoder.to(device)

    _vine_models['encoder'] = watermark_encoder
    _vine_models['decoder'] = decoder

    print('\n =================== All VINE Models Loaded Successfully ===================')


def crop_to_square(image):
    width, height = image.size
    min_side = min(width, height)
    left = (width - min_side) // 2
    top = (height - min_side) // 2
    right = left + min_side
    bottom = top + min_side
    return image.crop((left, top, right, bottom))


def watermark_image(image_path, output_dir, message=None):
    """Embed `message` into the image at `image_path` and write the result to
    `output_dir`. Returns (saved_path, bits_used, encoded_message). The
    encoded_message is the actual UTF-8 message stored (truncated to 12 bytes)."""
    device = _default_device()
    input_image_pil = Image.open(image_path).convert('RGB')
    if input_image_pil.size[0] != input_image_pil.size[1]:
        input_image_pil = crop_to_square(input_image_pil)

    size = input_image_pil.size
    t_val_256 = transforms.Compose([
        transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.ToTensor(),
    ])
    t_val_512 = transforms.Compose([
        transforms.Resize(size, interpolation=transforms.InterpolationMode.BICUBIC),
    ])

    resized_img = t_val_256(input_image_pil)
    resized_img = 2.0 * resized_img - 1.0
    input_image = transforms.ToTensor()(input_image_pil).unsqueeze(0).to(device)
    input_image = 2.0 * input_image - 1.0
    resized_img = resized_img.unsqueeze(0).to(device)

    bits = message_to_bits(message if message is not None else '')
    watermark = torch.tensor(bits, dtype=torch.float).unsqueeze(0).to(device)

    encoder = _vine_models.get('encoder')
    if encoder is None:
        raise RuntimeError("VINE encoder not initialized. Call setup_vine_models() first.")

    start_time = time.time()
    encoded_image_256 = encoder(resized_img, watermark)
    print(f'[vine] Encoding time: {time.time() - start_time:.2f}s')

    residual_256 = encoded_image_256 - resized_img
    residual_512 = t_val_512(residual_256)
    encoded_image = residual_512 + input_image
    encoded_image = encoded_image * 0.5 + 0.5
    encoded_image = torch.clamp(encoded_image, min=0.0, max=1.0)

    output_pil = transforms.ToPILImage()(encoded_image[0])
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    save_loc = os.path.join(output_dir, f'{base_name}_wm.png')
    output_pil.save(save_loc)

    gc.collect()
    _empty_cache()

    # Return the actual text that got stored (after UTF-8 truncation/padding).
    raw = (message if message is not None else '').encode('utf-8')[:MESSAGE_BYTES]
    encoded_message = raw.decode('utf-8', errors='replace').rstrip()

    return save_loc, bits, encoded_message


def decode_watermark(image_path, expected_message=None):
    """Decode bits from `image_path`. Returns a dict with:
      - bits: list[int] of length PAYLOAD_BITS
      - message: decoded UTF-8 message (may be garbled if no watermark present)
      - is_text: bool — True if decoded bytes look like real text
      - accuracy: float|None — bit accuracy vs `expected_message`, if provided
    """
    device = _default_device()
    t_val_256 = transforms.Compose([
        transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.ToTensor(),
    ])

    image = Image.open(image_path).convert("RGB")
    image = t_val_256(image).unsqueeze(0).to(device)

    decoder = _vine_models.get('decoder')
    if decoder is None:
        raise RuntimeError("VINE decoder not initialized. Call setup_vine_models() first.")

    pred = decoder(image)
    pred = np.array(pred[0].cpu().detach())
    pred = np.round(pred).astype(int)
    bits = pred.tolist()

    message, is_text = bits_to_message(bits)

    accuracy = None
    if expected_message is not None:
        expected_bits = message_to_bits(expected_message)
        n = min(len(expected_bits), len(bits))
        if n > 0:
            same = sum(1 for i in range(n) if expected_bits[i] == bits[i])
            accuracy = same / n

    return {
        'bits': bits,
        'message': message,
        'is_text': is_text,
        'accuracy': accuracy,
    }
