import time
from collections import defaultdict, deque

from fastapi import Depends, Request

from app.api.deps import SettingsDep, UserDep
from app.core.errors import AppError

MAX_TRACKED_KEYS = 10_000
LONGEST_WINDOW_SECONDS = 3600

_hits: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    _hits.clear()


def _forget_idle_keys(now: float) -> None:
    # Keys include submitted emails, so an attacker could otherwise grow this without limit.
    for key in [key for key, hits in _hits.items() if not hits or hits[-1] <= now - LONGEST_WINDOW_SECONDS]:
        del _hits[key]


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Sliding window held in this process; multiple workers would need a shared store."""
    now = time.monotonic()
    if len(_hits) > MAX_TRACKED_KEYS:
        _forget_idle_keys(now)
    hits = _hits[key]
    while hits and hits[0] <= now - window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        raise AppError(
            429, "rate_limited", "Too many requests. Please wait a moment and try again.", retryable=True
        )
    hits.append(now)


def limit_login(request: Request, settings: SettingsDep) -> None:
    client = request.client.host if request.client else "unknown"
    check_rate_limit(f"login:{client}", settings.login_attempts_per_minute, 60)


def limit_enrollment(user: UserDep, settings: SettingsDep) -> None:
    check_rate_limit(f"enroll:{user.id}", settings.enrollments_per_hour, 3600)


def limit_turns(user: UserDep, settings: SettingsDep) -> None:
    check_rate_limit(f"turn:{user.id}", settings.turns_per_minute, 60)


LoginLimit = Depends(limit_login)
EnrollmentLimit = Depends(limit_enrollment)
TurnLimit = Depends(limit_turns)
