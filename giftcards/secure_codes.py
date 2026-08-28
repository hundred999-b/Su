import base64
import hashlib
from cryptography.fernet import Fernet
from django.conf import settings


def _fernet():
    secret = str(settings.SECRET_KEY).encode('utf-8')
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_code(code: str) -> str:
    return _fernet().encrypt(code.strip().encode('utf-8')).decode('ascii')


def decrypt_code(value: str) -> str:
    return _fernet().decrypt(value.encode('ascii')).decode('utf-8')


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode('utf-8')).hexdigest()
