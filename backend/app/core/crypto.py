import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from ..config import get_settings


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.fernet_key.encode() if settings.fernet_key else base64.urlsafe_b64encode(
        hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
