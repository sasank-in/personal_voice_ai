import asyncio
import io
import re
import shutil
import subprocess
import wave

import imageio_ffmpeg

STT_SAMPLE_RATE = 16000


class InvalidAudioError(Exception):
    """The upload is empty, corrupt, or not decodable as audio."""


def ffmpeg_executable() -> str:
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def _convert_to_wav(audio_bytes: bytes, sample_rate: int) -> bytes:
    if not audio_bytes:
        raise InvalidAudioError("The recording is empty.")
    # subprocess.run in a worker thread: asyncio subprocesses need the
    # Proactor event loop on Windows, which uvicorn's reload mode does not use.
    result = subprocess.run(
        [
            ffmpeg_executable(),
            "-hide_banner",
            "-loglevel", "error",
            "-i", "pipe:0",
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "wav",
            "pipe:1",
        ],
        input=audio_bytes,
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0 or not result.stdout:
        raise InvalidAudioError("The file could not be decoded as audio.")
    return _rewrite_wav_header(result.stdout)


def _rewrite_wav_header(piped_wav: bytes) -> bytes:
    # FFmpeg cannot seek on a pipe, so its header has placeholder sizes.
    data_index = piped_wav.find(b"data")
    if data_index < 0:
        raise InvalidAudioError("The file could not be decoded as audio.")
    fmt_index = piped_wav.find(b"fmt ")
    channels = int.from_bytes(piped_wav[fmt_index + 10:fmt_index + 12], "little")
    sample_rate = int.from_bytes(piped_wav[fmt_index + 12:fmt_index + 16], "little")
    bits = int.from_bytes(piped_wav[fmt_index + 22:fmt_index + 24], "little")
    frames = piped_wav[data_index + 8:]
    if not frames:
        raise InvalidAudioError("The recording contains no audio.")

    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(bits // 8)
        writer.setframerate(sample_rate)
        writer.writeframes(frames)
    return output.getvalue()


async def normalize_to_wav(audio_bytes: bytes, sample_rate: int = STT_SAMPLE_RATE) -> bytes:
    return await asyncio.to_thread(_convert_to_wav, audio_bytes, sample_rate)


def wav_duration_seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
        return reader.getnframes() / reader.getframerate()


def merge_wavs(chunks: list[bytes]) -> bytes:
    """Join WAV files by their frames, since each chunk carries its own header."""
    if len(chunks) == 1:
        return chunks[0]

    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        for index, chunk in enumerate(chunks):
            with wave.open(io.BytesIO(chunk), "rb") as reader:
                if index == 0:
                    writer.setparams(reader.getparams())
                writer.writeframes(reader.readframes(reader.getnframes()))
    return output.getvalue()


_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def split_for_tts(text: str, limit: int = 1000) -> list[str]:
    """Split text into chunks of at most `limit` characters at sentence boundaries."""
    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text.strip()):
        for piece in _split_long_sentence(sentence, limit):
            if current and len(current) + 1 + len(piece) > limit:
                chunks.append(current)
                current = piece
            else:
                current = f"{current} {piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def _split_long_sentence(sentence: str, limit: int) -> list[str]:
    pieces: list[str] = []
    remaining = sentence
    while len(remaining) > limit:
        cut = remaining.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        pieces.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    if remaining:
        pieces.append(remaining)
    return pieces


_MARKDOWN = [
    (re.compile(r"```.*?```", re.DOTALL), " "),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE), ""),
    (re.compile(r"^\s*[-*+]\s+", re.MULTILINE), ""),
    (re.compile(r"(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1"), r"\2"),
]


def strip_markdown(text: str) -> str:
    for pattern, replacement in _MARKDOWN:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()
