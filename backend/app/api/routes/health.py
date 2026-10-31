from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep
from app.core.errors import AppError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: SessionDep) -> dict[str, str]:
    try:
        await session.execute(text("select 1"))
    except (SQLAlchemyError, OSError) as exc:
        raise AppError(503, "database_unavailable", "The database is unavailable.", retryable=True) from exc
    return {"status": "ok", "database": "ok"}
