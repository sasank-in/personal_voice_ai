"""Run STT -> LLM -> cloned TTS on one recording, using the saved voice.

Usage: python poc/check_pipeline.py recording.m4a [--language en-IN]
"""

import argparse
import asyncio
import time
from pathlib import Path

from _common import OUTPUT_DIR, load_voice_id

from app.core.config import get_settings
from app.services.providers.base import ProviderError
from app.services.providers.factory import build_llm, build_stt, build_voice
from app.utils.audio import merge_wavs, normalize_to_wav, split_for_tts, strip_markdown


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", type=Path)
    parser.add_argument("--language", default="en-IN")
    args = parser.parse_args()

    voice_id = load_voice_id()
    if not voice_id:
        print("No saved voice. Run check_sarvam_voice_clone.py first.")
        return 2

    settings = get_settings()
    try:
        started = time.perf_counter()
        wav = await normalize_to_wav(args.recording.read_bytes())
        transcription = await build_stt(settings).transcribe(wav, "utterance.wav", args.language)
        after_stt = time.perf_counter()
        print(f"[STT {after_stt - started:.2f}s] {transcription.text}")

        generated = await build_llm(settings).generate(
            f"You are a helpful personal voice assistant. Reply in {args.language}, in at most two spoken sentences.",
            [{"role": "user", "content": transcription.text}],
        )
        after_llm = time.perf_counter()
        print(f"[LLM {after_llm - after_stt:.2f}s] {generated.text}")

        voice = build_voice(settings)
        chunks = [
            (await voice.synthesize(voice_id, chunk, args.language)).audio
            for chunk in split_for_tts(strip_markdown(generated.text))
        ]
        path = OUTPUT_DIR / "pipeline_output.wav"
        path.write_bytes(merge_wavs(chunks))
        print(f"[TTS {time.perf_counter() - after_llm:.2f}s] {path}")
    except ProviderError as exc:
        print(f"FAILED at {exc.stage}: {exc.code} status={exc.status_code}: {exc.message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
