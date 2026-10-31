from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import SESSION_COOKIE, SessionDep, SettingsDep, UserDep
from app.core.errors import AppError
from app.core.rate_limit import LoginLimit
from app.core.security import create_session_token, verify_password
from app.models import User
from app.schemas.api import LoginRequest, UserOut, UserUpdate
from app.services.languages import VOICE_LANGUAGES

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=UserOut, dependencies=[LoginLimit])
async def login(body: LoginRequest, response: Response, session: SessionDep, settings: SettingsDep) -> User:
    user = await session.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")

    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id, settings.session_secret, settings.session_days),
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )
    return user


@router.post("/auth/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: UserDep) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(body: UserUpdate, user: UserDep, session: SessionDep) -> User:
    if body.language not in VOICE_LANGUAGES:
        raise AppError(400, "unsupported_language", "That language is not supported for voice cloning.")
    user.language = body.language
    await session.commit()
    return user


@router.get("/languages")
async def languages() -> dict[str, str]:
    return VOICE_LANGUAGES
