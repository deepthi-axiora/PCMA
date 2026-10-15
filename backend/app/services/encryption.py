import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


class EncryptionKeyUnavailable(RuntimeError):
    pass


def _cipher() -> AESGCM:
    encoded_key = settings.audio_encryption_key
    if not encoded_key:
        raise EncryptionKeyUnavailable("AUDIO_ENCRYPTION_KEY is not configured")
    try:
        key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise EncryptionKeyUnavailable("AUDIO_ENCRYPTION_KEY must be URL-safe base64") from exc
    if len(key) != 32:
        raise EncryptionKeyUnavailable("AUDIO_ENCRYPTION_KEY must decode to 32 bytes")
    return AESGCM(key)


def encrypt_bytes(plaintext: bytes, associated_data: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + _cipher().encrypt(nonce, plaintext, associated_data)


def decrypt_bytes(ciphertext: bytes, associated_data: bytes) -> bytes:
    if len(ciphertext) < 28:
        raise ValueError("Encrypted data is truncated")
    return _cipher().decrypt(ciphertext[:12], ciphertext[12:], associated_data)
