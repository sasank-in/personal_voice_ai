import base64
import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_password_hash = PasswordHash.recommended()
_DUMMY_HASH = _password_hash.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Do the same work for an unknown user, so timing does not reveal which emails exist."""
    try:
        matches = _password_hash.verify(password, password_hash or _DUMMY_HASH)
    except UnknownHashError:
        # A stored hash in an unrecognized format still costs one real verification.
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return matches and password_hash is not None


@dataclass(frozen=True)
class SessionClaims:
    session_id: uuid.UUID


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def create_session_token(session_id: uuid.UUID, expires_at: int, secret: str) -> str:
    payload = f"{session_id}.{expires_at}"
    return f"{payload}.{_sign(payload, secret)}"


def read_session_token(token: str, secret: str) -> SessionClaims | None:
    try:
        session_id, expires_at, signature = token.split(".")
    except ValueError:
        return None
    expected = _sign(f"{session_id}.{expires_at}", secret)
    # Compared as bytes: compare_digest raises on non-ASCII strings, which a client can send.
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        return None
    try:
        if int(expires_at) < time.time():
            return None
        return SessionClaims(uuid.UUID(session_id))
    except ValueError:
        return None
