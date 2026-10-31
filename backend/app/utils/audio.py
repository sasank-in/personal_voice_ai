import asyncio
import io
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg

STT_SAMPLE_RATE = 16000
DEFAULT_MAX_DECODE_SECONDS = 300
FFMPEG_TIMEOUT_SECONDS = 60
ALLOWED_DEMUXERS = "wav,mp3,ogg,flac,aac,aiff,amr,asf,matroska,webm,mov,mp4,m4a,3gp,3g2,mj2"


class InvalidAudioError(Exception):
    """The upload is empty, corrupt, or not decodable as audio."""


def ffmpeg_executable() -> str:
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def _convert_to_wav(audio_bytes: bytes, sample_rate: int, max_seconds: float) -> bytes:
    if not audio_bytes:
        raise InvalidAudioError("The recording is empty.")
    # Files rather than pipes: formats such as phone m4a keep their index at the end of the
    # file and need seeking. subprocess.run in a worker thread: asyncio subprocesses need the
    # Proactor event loop on Windows, which uvicorn's reload mode does not use.
    with tempfile.TemporaryDirectory(prefix="voice-ai-") as work:
        source = Path(work) / "input"
        target = Path(work) / "output.wav"
        source.write_bytes(audio_bytes)
        try:
            result = subprocess.run(
                [
                    ffmpeg_executable(),
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel", "error",
                    # Uploads are untrusted: no playlists or concat scripts that open other files.
                    "-format_whitelist", ALLOWED_DEMUXERS,
                    "-protocol_whitelist", "file",
                    "-i", str(source),
                    # Bounds memory and CPU for a small upload that decodes to hours of audio.
                    "-t", str(max_seconds),
                    "-vn",
                    "-map_metadata", "-1",
                    "-ac", "1",
                    "-ar", str(sample_rate),
                    "-f", "wav",
                    str(target),
                ],
                capture_output=True,
                timeout=FFMPEG_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise InvalidAudioError("The file took too long to process.") from exc
        if result.returncode != 0 or not target.exists():
            raise InvalidAudioError("The file could not be decoded as audio.")
        wav = target.read_bytes()

    if wav_duration_seconds(wav) == 0:
        raise InvalidAudioError("The recording contains no audio.")
    return wav


async def normalize_to_wav(
    audio_bytes: bytes,
    sample_rate: int = STT_SAMPLE_RATE,
    max_seconds: float = DEFAULT_MAX_DECODE_SECONDS,
) -> bytes:
    """Decode to mono WAV. Longer audio is cut at max_seconds, so set it above any length limit."""
    return await asyncio.to_thread(_convert_to_wav, audio_bytes, sample_rate, max_seconds)


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
    # Only at word edges, so "2*3*4" and "snake_case_name" keep their symbols.
    (re.compile(r"(?<![\w*])(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1(?![\w*])"), r"\2"),
]


def strip_markdown(text: str) -> str:
    for pattern, replacement in _MARKDOWN:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s+", " ", text).strip()
