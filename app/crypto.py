import base64
from cryptography.fernet import Fernet
from .settings import settings

def _fernet() -> Fernet:
    # Derive a 32-byte urlsafe key from SECRET_KEY (not perfect, but fine for a dev challenge).
    key = settings.SECRET_KEY.encode("utf-8")
    # pad/trim to 32 bytes then base64 urlsafe
    key32 = (key * (32 // len(key) + 1))[:32]
    return Fernet(base64.urlsafe_b64encode(key32))

def encrypt_str(s: str) -> str:
    return _fernet().encrypt(s.encode("utf-8")).decode("utf-8")

def decrypt_str(s: str) -> str:
    return _fernet().decrypt(s.encode("utf-8")).decode("utf-8")
