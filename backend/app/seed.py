"""Create an account, or reset an existing account's password, from the command line.

Usage: python -m app.seed --email you@example.com
The password is read from SEED_USER_PASSWORD, or prompted for.
"""

import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import User
from app.schemas.api import normalize_email
from app.services.account_service import end_all_sessions


async def upsert_user(email: str, password: str) -> bool:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
        created = user is None
        if created:
            session.add(User(email=email, password_hash=hash_password(password)))
            await session.commit()
        else:
            user.password_hash = hash_password(password)
            await session.commit()
            # A password reset logs the account out everywhere.
            await end_all_sessions(session, user.id)
    await engine.dispose()
    return created


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=settings.seed_user_email)
    args = parser.parse_args()

    try:
        email = normalize_email(args.email)
    except ValueError:
        raise SystemExit("Enter a valid email address.")
    password = settings.seed_user_password or getpass.getpass("Password: ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")

    created = asyncio.run(upsert_user(email, password))
    print(f"{'Created' if created else 'Updated'} user {email}")


if __name__ == "__main__":
    main()
