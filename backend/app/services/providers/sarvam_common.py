import httpx
from sarvamai import AsyncSarvamAI
from sarvamai.core.api_error import ApiError

from app.services.providers.base import ProviderError


def build_client(api_key: str | None, timeout_seconds: float) -> AsyncSarvamAI:
    if not api_key:
        raise ProviderError(
            "provider_not_configured", "SARVAM_API_KEY is not configured.", stage="configuration"
        )
    return AsyncSarvamAI(api_subscription_key=api_key, timeout=timeout_seconds)


def map_error(exc: Exception, stage: str, failure_code: str, failure_message: str) -> ProviderError:
    if isinstance(exc, httpx.TimeoutException):
        return ProviderError(
            "provider_timeout", "The voice service timed out.", stage=stage, retryable=True
        )
    if isinstance(exc, httpx.HTTPError):
        return ProviderError(
            "provider_unavailable", "The voice service is unreachable.", stage=stage, retryable=True
        )
    if not isinstance(exc, ApiError):
        return ProviderError(failure_code, failure_message, stage=stage)

    status = exc.status_code
    body = str(exc.body)
    if status == 400 and "Voice not found" in body:
        return ProviderError(
            "voice_not_found",
            "This voice no longer exists at Sarvam. Delete this profile and create it again.",
            stage=stage,
            status_code=status,
        )
    if status == 403 and "TIER_LIMIT_REACHED" in body:
        return ProviderError(
            "voice_limit_reached", "The saved voice limit has been reached.", stage=stage, status_code=status
        )
    if status in (401, 403):
        return ProviderError(
            "provider_auth_failed",
            "The voice service rejected the configured credentials or this feature is not enabled.",
            stage=stage,
            status_code=status,
        )
    if status == 402:
        return ProviderError(
            "provider_quota_exceeded", "The voice service quota is exhausted.", stage=stage, status_code=status
        )
    if status == 429:
        return ProviderError(
            "provider_rate_limited", "The voice service is rate limited.", stage=stage, retryable=True, status_code=status
        )
    if status is not None and status >= 500:
        return ProviderError(
            "provider_unavailable", "The voice service is unavailable.", stage=stage, retryable=True, status_code=status
        )
    return ProviderError(failure_code, failure_message, stage=stage, status_code=status)
