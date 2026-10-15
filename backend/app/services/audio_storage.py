import os
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.services.encryption import EncryptionKeyUnavailable, decrypt_bytes, encrypt_bytes


class AudioStorageNotConfigured(RuntimeError):
    pass


def _path(storage_ref: str) -> Path:
    root = Path(settings.audio_storage_dir).resolve()
    path = (root / storage_ref).resolve()
    if path.parent != root or not storage_ref.endswith(".enc"):
        raise ValueError("Invalid audio storage reference")
    return path


def store_encrypted_audio(plaintext: bytes) -> str:
    storage_ref = f"{uuid4().hex}.enc"
    path = _path(storage_ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        encrypted = encrypt_bytes(plaintext, storage_ref.encode("ascii"))
    except EncryptionKeyUnavailable as exc:
        raise AudioStorageNotConfigured(str(exc)) from exc
    temporary = path.with_suffix(".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(encrypted)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return storage_ref


def read_encrypted_audio(storage_ref: str) -> bytes:
    encrypted = _path(storage_ref).read_bytes()
    try:
        return decrypt_bytes(encrypted, storage_ref.encode("ascii"))
    except EncryptionKeyUnavailable as exc:
        raise AudioStorageNotConfigured(str(exc)) from exc


def delete_audio(storage_ref: str) -> None:
    path = _path(storage_ref)
    if path.exists():
        path.unlink()
