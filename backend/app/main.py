import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audio, auth, conversations, health, voices
from app.core.config import DEV_SESSION_SECRET, get_settings
from app.core.errors import register_error_handlers

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
# Request logs from these clients are not needed and can include sensitive URLs.
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.is_production and settings.session_secret == DEV_SESSION_SECRET:
        raise RuntimeError("Set SESSION_SECRET before running in production.")

    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    for module in (health, auth, voices, conversations, audio):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
