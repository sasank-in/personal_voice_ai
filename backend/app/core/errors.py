import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.providers.base import ProviderError
from app.utils.audio import InvalidAudioError

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        stage: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.stage = stage
        self.retryable = retryable


def not_found(what: str) -> AppError:
    return AppError(404, "not_found", f"{what} not found.")


PROVIDER_ERROR_STATUS = {
    "provider_rate_limited": 429,
    "voice_limit_reached": 409,
    "voice_sample_rejected": 422,
    "empty_transcript": 422,
}


def provider_error_status(exc: ProviderError) -> int:
    if exc.code in PROVIDER_ERROR_STATUS:
        return PROVIDER_ERROR_STATUS[exc.code]
    # A provider's 401 must not reach the browser as a 401: the user is logged in.
    return 503 if exc.retryable else 502


def error_body(
    code: str, message: str, stage: str | None = None, retryable: bool = False
) -> dict:
    return {"error": {"code": code, "message": message, "stage": stage, "retryable": retryable}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            error_body(exc.code, exc.message, exc.stage, exc.retryable),
            status_code=exc.status_code,
        )

    @app.exception_handler(ProviderError)
    async def handle_provider_error(_: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(
            error_body(exc.code, exc.message, exc.stage, exc.retryable),
            status_code=provider_error_status(exc),
        )

    @app.exception_handler(InvalidAudioError)
    async def handle_invalid_audio(_: Request, exc: InvalidAudioError) -> JSONResponse:
        return JSONResponse(
            error_body("invalid_audio", f"{exc} Please record again.", "uploading"),
            status_code=400,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            error_body("internal_error", "Something went wrong. Please try again.", retryable=True),
            status_code=500,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"][1:]) or "request"
        return JSONResponse(
            error_body("invalid_request", f"{field}: {first['msg']}"),
            status_code=422,
        )
