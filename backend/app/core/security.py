import base64
import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
_DUMMY_HASH = _password_hash.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


"""
def verify_password(password: str, password_hash: str | None) -> bool:
    # Do the same work for an unknown user, so timing does not reveal which emails exist.
    matches = _password_hash.verify(password, password_hash or _DUMMY_HASH)
    return matches and password_hash is not None
"""

from pwdlib.exceptions import UnknownHashError

def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify password while avoiding email enumeration timing differences."""
    try:
        matches = _password_hash.verify(
            password,
            password_hash or _DUMMY_HASH
        )
        return matches and password_hash is not None

    except UnknownHashError:
        return False

@dataclass(frozen=True)
class SessionClaims:
    user_id: uuid.UUID
    version: int


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def create_session_token(user_id: uuid.UUID, version: int, secret: str, days: int) -> str:
    expires_at = int(time.time()) + days * 86400
    payload = f"{user_id}.{version}.{expires_at}"
    return f"{payload}.{_sign(payload, secret)}"


def read_session_token(token: str, secret: str) -> SessionClaims | None:
    try:
        user_id, version, expires_at, signature = token.split(".")
    except ValueError:
        return None
    expected = _sign(f"{user_id}.{version}.{expires_at}", secret)
    # Compared as bytes: compare_digest raises on non-ASCII strings, which a client can send.
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        return None
    try:
        if int(expires_at) < time.time():
            return None
        return SessionClaims(uuid.UUID(user_id), int(version))
    except ValueError:
        return None
