import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audio, auth, conversations, health, voices
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.middleware import register_request_guards

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
# Request logs from these clients are not needed and can include sensitive URLs.
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title=settings.app_name, **docs)
    register_request_guards(app, settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(app)
    for module in (health, auth, voices, conversations, audio):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
