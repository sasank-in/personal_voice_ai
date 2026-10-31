import openai

from app.services.providers.base import ProviderError, ProviderUsage


def response_usage(response, input_tokens: int | None = None, output_tokens: int | None = None) -> ProviderUsage:
    # _request_id is the SDK's documented accessor for the x-request-id response header.
    request_id = getattr(response, "_request_id", None) or getattr(response, "id", None)
    return ProviderUsage(request_id=request_id, input_tokens=input_tokens, output_tokens=output_tokens)


def map_openai_error(exc: openai.APIError, stage: str, service: str, failure_code: str, failure_message: str) -> ProviderError:
    request_id = getattr(exc, "request_id", None)
    if isinstance(exc, openai.AuthenticationError):
        return ProviderError(
            "provider_auth_failed", f"The {service} rejected the configured key.", stage=stage, status_code=401, request_id=request_id
        )
    if isinstance(exc, openai.RateLimitError):
        return ProviderError(
            "provider_rate_limited", f"The {service} is rate limited.", stage=stage, retryable=True, status_code=429, request_id=request_id
        )
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError)):
        return ProviderError(
            "provider_unavailable", f"The {service} is unavailable.", stage=stage, retryable=True, request_id=request_id
        )
    return ProviderError(
        failure_code, failure_message, stage=stage, status_code=getattr(exc, "status_code", None), request_id=request_id
    )
