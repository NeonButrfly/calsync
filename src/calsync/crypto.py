from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet


def _build_fernet(key_material: str) -> Fernet:
    normalized_key = key_material.strip()
    if not normalized_key:
        raise ValueError("Encryption key material must not be blank.")

    derived_key = urlsafe_b64encode(sha256(normalized_key.encode("utf-8")).digest())
    return Fernet(derived_key)


def encrypt_text(key_material: str, plaintext: str) -> str:
    return _build_fernet(key_material).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(key_material: str, ciphertext: str) -> str:
    return _build_fernet(key_material).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
