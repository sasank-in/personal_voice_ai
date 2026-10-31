from typing import Annotated

from fastapi import APIRouter, Cookie, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import SESSION_COOKIE, SessionDep, SettingsDep, UserDep
from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import LoginLimit, check_rate_limit
from app.core.security import create_session_token, hash_password, read_session_token, verify_password
from app.models import User
from app.schemas.api import LoginRequest, PasswordChange, SignupRequest, UserOut, UserUpdate
from app.services.languages import VOICE_LANGUAGES

router = APIRouter(tags=["auth"])


def set_session_cookie(response: Response, user: User, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user.id, user.session_version, settings.session_secret, settings.session_days),
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )


@router.post("/auth/signup", response_model=UserOut, status_code=201, dependencies=[LoginLimit])
async def signup(
    body: SignupRequest, response: Response, session: SessionDep, settings: SettingsDep
) -> User:
    email = body.email
    check_rate_limit(f"signup-email:{email}", settings.login_attempts_per_minute, 60)

    existing_user_id = await session.scalar(select(User.id).where(User.email == email))
    if existing_user_id is not None:
        raise AppError(409, "email_already_registered", "An account with this email already exists.")

    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        existing_user_id = await session.scalar(select(User.id).where(User.email == email))
        if existing_user_id is None:
            raise
        raise AppError(409, "email_already_registered", "An account with this email already exists.") from exc

    set_session_cookie(response, user, settings)
    return user


@router.post("/auth/login", response_model=UserOut, dependencies=[LoginLimit])
async def login(body: LoginRequest, response: Response, session: SessionDep, settings: SettingsDep) -> User:
    email = body.email.strip().lower()
    check_rate_limit(f"login-email:{email}", settings.login_attempts_per_minute, 60)

    user = await session.scalar(select(User).where(User.email == email))
    if not verify_password(body.password, user.password_hash if user else None):
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")

    set_session_cookie(response, user, settings)
    return user


@router.post("/auth/logout", status_code=204)
async def logout(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    claims = read_session_token(token, settings.session_secret) if token else None
    user = await session.get(User, claims.user_id) if claims else None
    # Revokes the token itself, so a copied cookie stops working too.
    if user is not None and user.session_version == claims.version:
        user.session_version += 1
        await session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.post("/me/password", status_code=204, dependencies=[LoginLimit])
async def change_password(
    body: PasswordChange, response: Response, user: UserDep, session: SessionDep, settings: SettingsDep
) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise AppError(400, "invalid_credentials", "Your current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    # Ends every other session, and keeps this one logged in.
    user.session_version += 1
    await session.commit()
    set_session_cookie(response, user, settings)


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
