from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.errors import error_body

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
JSON_BODY_LIMIT = 1024 * 1024
MULTIPART_OVERHEAD = 1024 * 1024

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def _body_error(request: Request, settings: Settings) -> JSONResponse | None:
    """Reject oversized bodies up front: FastAPI parses them before any dependency runs."""
    declared = request.headers.get("content-length")
    if declared is None:
        if request.headers.get("transfer-encoding"):
            return JSONResponse(error_body("length_required", "Content-Length is required."), status_code=411)
        return None

    is_upload = request.headers.get("content-type", "").startswith("multipart/form-data")
    limit = settings.max_audio_upload_mb * 1024 * 1024 + MULTIPART_OVERHEAD if is_upload else JSON_BODY_LIMIT
    if not declared.isdigit() or int(declared) > limit:
        return JSONResponse(
            error_body("file_too_large", f"Uploads must be under {settings.max_audio_upload_mb} MB.", "uploading"),
            status_code=413,
        )
    return None


def register_request_guards(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def guard(request: Request, call_next):
        response = None
        if request.method in UNSAFE_METHODS:
            # SameSite=Lax treats other localhost ports as same-site, so the Origin is checked too.
            origin = request.headers.get("origin")
            if origin is not None and origin not in settings.cors_origin_list:
                response = JSONResponse(
                    error_body("origin_not_allowed", "Requests from this origin are not allowed."),
                    status_code=403,
                )
            else:
                response = _body_error(request, settings)

        if response is None:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response
