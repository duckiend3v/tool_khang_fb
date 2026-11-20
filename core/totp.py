"""Small, dependency-free TOTP helper used by the manual 2FA panel."""

import base64
import hashlib
import hmac
import re
import struct
import time
from urllib.parse import parse_qs, urlparse


def normalize_totp_secret(value):
    """Return a normalized Base32 secret from raw text or an otpauth URI."""
    raw = str(value or "").strip()
    if raw.lower().startswith("otpauth://"):
        raw = parse_qs(urlparse(raw).query).get("secret", [""])[0]

    secret = re.sub(r"[\s-]", "", raw).upper()
    if not secret or not re.fullmatch(r"[A-Z2-7]+=*", secret):
        raise ValueError("Secret không phải Base32 hợp lệ")
    return secret + "=" * ((8 - len(secret) % 8) % 8)


def generate_totp(secret, timestamp=None, digits=6, period=30):
    """Generate a TOTP value locally without sending the secret over the network."""
    normalized = normalize_totp_secret(secret)
    key = base64.b32decode(normalized, casefold=True)
    now = time.time() if timestamp is None else float(timestamp)
    counter = int(now // period)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24)
        | (digest[offset + 1] << 16)
        | (digest[offset + 2] << 8)
        | digest[offset + 3]
    )
    return f"{binary % (10 ** digits):0{digits}d}"


def totp_seconds_remaining(timestamp=None, period=30):
    now = time.time() if timestamp is None else float(timestamp)
    return period - (int(now) % period)
