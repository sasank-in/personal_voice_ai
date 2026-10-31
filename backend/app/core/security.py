import base64
import hashlib
import hmac
import time
import uuid

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def create_session_token(user_id: uuid.UUID, secret: str, days: int) -> str:
    expires_at = int(time.time()) + days * 86400
    payload = f"{user_id}.{expires_at}"
    return f"{payload}.{_sign(payload, secret)}"


def read_session_token(token: str, secret: str) -> uuid.UUID | None:
    try:
        user_id, expires_at, signature = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(f"{user_id}.{expires_at}", secret)):
        return None
    try:
        if int(expires_at) < time.time():
            return None
        return uuid.UUID(user_id)
    except ValueError:
        return None
