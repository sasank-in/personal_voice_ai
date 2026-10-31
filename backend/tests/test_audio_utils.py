import pytest

from app.utils.audio import (
    InvalidAudioError,
    merge_wavs,
    normalize_to_wav,
    split_for_tts,
    strip_markdown,
    wav_duration_seconds,
)
from tests.conftest import make_wav


def test_split_keeps_every_chunk_within_limit():
    text = " ".join(f"Sentence number {i} is here." for i in range(200))
    chunks = split_for_tts(text, limit=100)
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert " ".join(chunks) == text


def test_split_handles_long_text_without_sentence_breaks():
    chunks = split_for_tts("word " * 500, limit=100)
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_split_handles_a_single_unbroken_token():
    chunks = split_for_tts("x" * 250, limit=100)
    assert [len(chunk) for chunk in chunks] == [100, 100, 50]


def test_split_of_short_text_is_one_chunk():
    assert split_for_tts("Hello there.") == ["Hello there."]


def test_merge_wavs_adds_durations_and_stays_valid():
    merged = merge_wavs([make_wav(0.5), make_wav(0.25)])
    assert wav_duration_seconds(merged) == pytest.approx(0.75, abs=0.01)


def test_strip_markdown_leaves_speakable_text():
    text = "## Title\n\n**Bold** and `code` with [a link](https://example.com)\n- item"
    assert strip_markdown(text) == "Title Bold and code with a link item"


async def test_normalize_converts_webm_to_mono_16k_wav():
    import subprocess

    from app.utils.audio import ffmpeg_executable

    webm = subprocess.run(
        [ffmpeg_executable(), "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
         "-c:a", "libopus", "-f", "webm", "pipe:1"],
        capture_output=True,
        check=True,
    ).stdout
    wav = await normalize_to_wav(webm)
    assert wav[:4] == b"RIFF"
    assert wav_duration_seconds(wav) == pytest.approx(2.0, abs=0.1)


async def test_normalize_rejects_garbage_and_empty_input():
    with pytest.raises(InvalidAudioError):
        await normalize_to_wav(b"this is not audio at all" * 100)
    with pytest.raises(InvalidAudioError):
        await normalize_to_wav(b"")
