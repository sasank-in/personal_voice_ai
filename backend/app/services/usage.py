import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProviderRequest
from app.services.providers.base import ProviderError, ProviderUsage

logger = logging.getLogger(__name__)

T = TypeVar("T")


class UsageRecorder:
    """Records one row per provider call: its request ID, usage, latency and outcome."""

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._pending: list[ProviderRequest] = []

    async def track(
        self,
        provider: str,
        operation: str,
        call: Callable[[], Awaitable[T]],
        *,
        model: str | None = None,
        input_characters: int | None = None,
        audio_seconds: float | None = None,
    ) -> T:
        await self.release_connection()
        try:
            return await self.measure(
                provider, operation, call, model=model, input_characters=input_characters, audio_seconds=audio_seconds
            )
        finally:
            await self.flush()

    async def release_connection(self) -> None:
        # Ends the open transaction, so no database connection is held during a slow provider call.
        await self._session.commit()

    async def measure(
        self,
        provider: str,
        operation: str,
        call: Callable[[], Awaitable[T]],
        *,
        model: str | None = None,
        input_characters: int | None = None,
        audio_seconds: float | None = None,
    ) -> T:
        """Run one call without touching the session, so calls can safely run in parallel."""
        usage = ProviderUsage()
        started = time.perf_counter()
        status = "ok"
        try:
            result = await call()
            usage = getattr(result, "usage", usage)
            return result
        except ProviderError as exc:
            status = exc.code
            usage = ProviderUsage(request_id=exc.request_id)
            raise
        except Exception:
            status = "unexpected_error"
            raise
        finally:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s %s %.0fms request_id=%s", provider, operation, status, latency_ms, usage.request_id
            )
            self._pending.append(
                ProviderRequest(
                    user_id=self._user_id,
                    provider=provider,
                    operation=operation,
                    provider_request_id=usage.request_id,
                    model=model,
                    input_characters=input_characters,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    audio_seconds=audio_seconds,
                    latency_ms=latency_ms,
                    status=status,
                )
            )

    async def flush(self) -> None:
        # Bookkeeping must never fail a turn or hide the provider's real error.
        rows, self._pending = self._pending, []
        try:
            self._session.add_all(rows)
            await self._session.commit()
        except SQLAlchemyError:
            logger.exception("Could not save provider usage")
            await self._session.rollback()
