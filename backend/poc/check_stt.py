"""Transcribe a recording with the configured STT provider.

Usage: python poc/check_stt.py recording.m4a [--language en-IN]
"""

import argparse
import asyncio
import time
from pathlib import Path

import _common  # noqa: F401

from app.core.config import get_settings
from app.services.providers.base import ProviderError
from app.services.providers.factory import build_stt
from app.utils.audio import InvalidAudioError, normalize_to_wav


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", type=Path)
    parser.add_argument("--language", default="en-IN")
    args = parser.parse_args()

    settings = get_settings()
    print(f"provider={settings.stt_provider} model={settings.resolved_stt_model}")
    started = time.perf_counter()
    try:
        wav = await normalize_to_wav(args.recording.read_bytes())
        result = await build_stt(settings).transcribe(wav, "utterance.wav", args.language)
    except InvalidAudioError as exc:
        print(f"FAILED: {exc}")
        return 1
    except ProviderError as exc:
        print(f"FAILED {exc.code} status={exc.status_code} request_id={exc.request_id}: {exc.message}")
        return 1
    print(f"OK in {time.perf_counter() - started:.2f}s: {result.text}")
    print(f"usage: {result.usage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
