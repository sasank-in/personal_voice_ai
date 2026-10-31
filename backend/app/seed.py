"""Create or update the single MVP user.

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


async def upsert_user(email: str, password: str) -> bool:
    email = email.strip().lower()
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
        created = user is None
        if created:
            user = User(email=email, password_hash=hash_password(password))
            session.add(user)
        else:
            user.password_hash = hash_password(password)
            user.session_version += 1
        await session.commit()
    await engine.dispose()
    return created


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=settings.seed_user_email)
    args = parser.parse_args()

    password = settings.seed_user_password or getpass.getpass("Password: ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")

    created = asyncio.run(upsert_user(args.email, password))
    print(f"{'Created' if created else 'Updated'} user {args.email}")


if __name__ == "__main__":
    main()
