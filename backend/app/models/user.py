import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utc_now
from app.services.languages import LANGUAGE_CHECK


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(LANGUAGE_CHECK, name="ck_users_language"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(16), default="en-IN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
