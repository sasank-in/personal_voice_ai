"""Send a simple prompt to the configured LLM and print the reply.

Usage: python poc/check_llm.py
"""

import asyncio
import time

import _common  # noqa: F401

from app.core.config import get_settings
from app.services.providers.base import ProviderError
from app.services.providers.factory import build_llm


async def main() -> int:
    settings = get_settings()
    print(f"provider={settings.llm_provider} model={settings.resolved_llm_model}")
    started = time.perf_counter()
    try:
        reply = await build_llm(settings).generate(
            "You are a helpful assistant. Reply in one short sentence.",
            [{"role": "user", "content": "Say hello and name one planet."}],
        )
    except ProviderError as exc:
        print(f"FAILED {exc.code}: {exc.message}")
        return 1
    print(f"OK in {time.perf_counter() - started:.2f}s: {reply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
