from typing import Annotated

from fastapi import APIRouter, Cookie, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import SESSION_COOKIE, AuthDep, ProvidersDep, SessionDep, SettingsDep, StoreDep, UserDep
from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import LoginLimit, check_rate_limit
from app.core.security import hash_password, read_session_token, verify_password
from app.models import User, VoiceProfile
from app.schemas.api import (
    AccountDeletion,
    AuthOptions,
    LoginRequest,
    PasswordChange,
    SignupRequest,
    UserOut,
    UserUpdate,
)
from app.services import account_service
from app.services.languages import VOICE_LANGUAGES

router = APIRouter(tags=["auth"])


async def log_in(response: Response, session: SessionDep, user: User, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        await account_service.start_session(session, user, settings),
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/auth/options", response_model=AuthOptions)
async def options(settings: SettingsDep) -> AuthOptions:
    return AuthOptions(signup_enabled=settings.signup_enabled)


@router.post("/auth/signup", response_model=UserOut, status_code=201, dependencies=[LoginLimit])
async def signup(
    body: SignupRequest, response: Response, session: SessionDep, settings: SettingsDep
) -> User:
    # Every account can spend provider credits, so a public deployment may need sign-up off.
    if not settings.signup_enabled:
        raise AppError(403, "signup_disabled", "Sign-up is turned off. Ask the owner for an account.")
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

    await log_in(response, session, user, settings)
    return user


@router.post("/auth/login", response_model=UserOut, dependencies=[LoginLimit])
async def login(body: LoginRequest, response: Response, session: SessionDep, settings: SettingsDep) -> User:
    email = body.email.strip().lower()
    check_rate_limit(f"login-email:{email}", settings.login_attempts_per_minute, 60)

    user = await session.scalar(select(User).where(User.email == email))
    if not verify_password(body.password, user.password_hash if user else None):
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")

    await log_in(response, session, user, settings)
    return user


@router.post("/auth/logout", status_code=204)
async def logout(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    """Logs out this device only, and the copied cookie stops working too."""
    claims = read_session_token(token, settings.session_secret) if token else None
    if claims:
        await account_service.end_session(session, claims.session_id)
    clear_cookie(response)


@router.post("/auth/logout-everywhere", status_code=204)
async def logout_everywhere(response: Response, auth: AuthDep, session: SessionDep) -> None:
    await account_service.end_all_sessions(session, auth.user.id)
    clear_cookie(response)


@router.post("/me/password", status_code=204, dependencies=[LoginLimit])
async def change_password(body: PasswordChange, auth: AuthDep, session: SessionDep) -> None:
    user = auth.user
    if not verify_password(body.current_password, user.password_hash):
        raise AppError(400, "invalid_credentials", "Your current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    await session.commit()
    # Ends every other session and keeps this one logged in.
    await account_service.end_all_sessions(session, user.id, keep=auth.session_id)


@router.delete("/me", status_code=204, dependencies=[LoginLimit])
async def delete_account(
    body: AccountDeletion,
    response: Response,
    user: UserDep,
    session: SessionDep,
    store: StoreDep,
    providers: ProvidersDep,
) -> None:
    if not verify_password(body.password, user.password_hash):
        raise AppError(400, "invalid_credentials", "Your password is incorrect.")
    has_cloned_voice = await session.scalar(
        select(VoiceProfile.id).where(VoiceProfile.user_id == user.id, VoiceProfile.provider_voice_id.is_not(None)).limit(1)
    )
    voice = providers.voice() if has_cloned_voice else None
    await account_service.delete_account(session, voice, store, user)
    clear_cookie(response)


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
