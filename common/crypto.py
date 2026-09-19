"""Shared crypto helpers used by both the issuers and documents apps.

Kept outside any single Django app to avoid circular imports between
`issuers` (owns RSA keypairs) and `documents` (verifies signatures + encrypts
file bytes).

Everything here uses the standard `cryptography` library only (BSD/Apache-2.0
licensed, no paid service, no external CA) which is what makes the "digital
signature" verification free to run end-to-end.
"""

import base64
import hashlib
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.utils import OperationalError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

NONCE_SIZE = 12  # 96-bit nonce, recommended size for AES-GCM


def get_master_key() -> bytes:
    """The server-side master key used to envelope-encrypt data keys and private keys."""
    raw = settings.MASTER_ENCRYPTION_KEY
    if not raw:
        raise ImproperlyConfigured(
            'MASTER_ENCRYPTION_KEY is not set. Generate one with:\n'
            '  py -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"\n'
            'and put it in your .env file.'
        )
    key = base64.urlsafe_b64decode(raw)
    if len(key) != 32:
        raise ImproperlyConfigured('MASTER_ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256).')
    return key


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def aes_encrypt(key: bytes, plaintext: bytes, associated_data: bytes = None):
    """AES-256-GCM encrypt. Returns (nonce, ciphertext_with_tag)."""
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, associated_data)
    return nonce, ciphertext


def aes_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, associated_data: bytes = None) -> bytes:
    return AESGCM(key).decrypt(nonce, ciphertext, associated_data)


def generate_data_key() -> bytes:
    """A fresh random AES-256 key, unique per document (envelope encryption)."""
    return AESGCM.generate_key(bit_length=256)


def generate_rsa_keypair():
    """RSA-2048 keypair for an Issuer. Self-issued, no paid CA/DSC required."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def sign_bytes(private_pem: bytes, data: bytes) -> bytes:
    private_key = serialization.load_pem_private_key(private_pem, password=None)
    return private_key.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def verify_signature(public_pem: bytes, data: bytes, signature: bytes) -> bool:
    """Automated, admin-free verification: true only if `signature` was produced by
    the holder of the private key matching `public_pem` over exactly these bytes."""
    public_key = serialization.load_pem_public_key(public_pem)
    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return True
    except InvalidSignature:
        return False


# Exponential-backoff retry for transient storage/DB errors, e.g. a momentary
# connection-pool exhaustion behind PgBouncer or a disk I/O hiccup.
retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    retry=retry_if_exception_type((OSError, IOError, OperationalError)),
)
