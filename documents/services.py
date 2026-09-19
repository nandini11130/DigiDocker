"""Envelope-encryption + retry helpers specific to storing/reading Document files."""

from common.crypto import aes_decrypt, aes_encrypt, generate_data_key, get_master_key, retry_transient, sha256_hex


def encrypt_file_for_storage(raw_bytes: bytes) -> dict:
    data_key = generate_data_key()
    file_nonce, ciphertext = aes_encrypt(data_key, raw_bytes)
    key_nonce, key_ciphertext = aes_encrypt(get_master_key(), data_key)
    return {
        'ciphertext': ciphertext,
        'file_nonce': file_nonce,
        'data_key_nonce': key_nonce,
        'data_key_ciphertext': key_ciphertext,
        'sha256': sha256_hex(raw_bytes),
    }


@retry_transient
def decrypt_document_file(document) -> bytes:
    data_key = aes_decrypt(get_master_key(), bytes(document.data_key_nonce), bytes(document.data_key_ciphertext))
    document.encrypted_file.open('rb')
    try:
        ciphertext = document.encrypted_file.read()
    finally:
        document.encrypted_file.close()
    return aes_decrypt(data_key, bytes(document.file_nonce), ciphertext)
