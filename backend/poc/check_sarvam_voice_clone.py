"""Create a voice from your own sample once, then synthesize a phrase with it.

Usage:
  python poc/check_sarvam_voice_clone.py --sample my_voice.m4a --i-own-this-voice
  python poc/check_sarvam_voice_clone.py            (reuses the saved voice)
  python poc/check_sarvam_voice_clone.py --delete   (deletes the saved voice)
"""

import argparse
import asyncio
import time
import uuid
from pathlib import Path

from _common import OUTPUT_DIR, VOICE_STATE, load_voice_id, save_voice_id

from app.core.config import get_settings
from app.services.providers.base import ProviderError
from app.services.providers.factory import build_voice
from app.utils.audio import InvalidAudioError, normalize_to_wav, wav_duration_seconds


async def run(args: argparse.Namespace) -> int:
    voice = build_voice(get_settings())
    voice_id = load_voice_id()

    if args.delete:
        if not voice_id:
            print("No saved voice to delete.")
            return 0
        await voice.delete_voice(voice_id)
        VOICE_STATE.unlink()
        print("OK: voice deleted at the provider.")
        return 0

    if not voice_id:
        if not args.sample:
            print("No saved voice. Pass --sample and --i-own-this-voice to create one.")
            return 2
        if not args.i_own_this_voice:
            print("Refusing to clone without --i-own-this-voice: only clone a voice you have the right to use.")
            return 2
        wav = await normalize_to_wav(args.sample.read_bytes(), sample_rate=args.sample_rate)
        print(f"sample: {wav_duration_seconds(wav):.1f}s at {args.sample_rate} Hz")
        created = await voice.create_voice(wav, "sample.wav", f"poc-{uuid.uuid4()}", args.language)
        voice_id = created.provider_voice_id
        save_voice_id(voice_id)
        print(f"voice created; reference text: {created.reference_text}")

    started = time.perf_counter()
    result = await voice.synthesize(voice_id, args.text, args.language)
    path = OUTPUT_DIR / "clone_output.wav"
    path.write_bytes(result.audio)
    print(f"OK in {time.perf_counter() - started:.2f}s: {wav_duration_seconds(result.audio):.1f}s of audio at {path}")
    print(f"usage: {result.usage}")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=Path)
    parser.add_argument("--i-own-this-voice", action="store_true")
    parser.add_argument("--language", default="en-IN")
    parser.add_argument("--sample-rate", type=int, default=24000)
    parser.add_argument("--text", default="Hello! This is a test of my personal voice assistant.")
    parser.add_argument("--delete", action="store_true")
    args = parser.parse_args()
    try:
        return await run(args)
    except InvalidAudioError as exc:
        print(f"FAILED: {exc}")
    except ProviderError as exc:
        print(f"FAILED {exc.code} status={exc.status_code}: {exc.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
