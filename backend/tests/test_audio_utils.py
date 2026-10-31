import subprocess

import pytest

from app.utils.audio import (
    InvalidAudioError,
    ffmpeg_executable,
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


def test_strip_markdown_keeps_maths_and_identifiers():
    assert strip_markdown("2*3*4 is 24") == "2*3*4 is 24"
    assert strip_markdown("use snake_case_name here") == "use snake_case_name here"
    assert strip_markdown("an *emphasized* word and __another__") == "an emphasized word and another"


def encode(tmp_path, name, *ffmpeg_args):
    path = tmp_path / name
    subprocess.run(
        [ffmpeg_executable(), "-y", "-loglevel", "error", *ffmpeg_args, str(path)], check=True
    )
    return path


async def test_phone_m4a_with_index_at_the_end_decodes_fully(tmp_path):
    path = encode(tmp_path, "phone.m4a", "-f", "lavfi", "-i", "anoisesrc=d=60:c=pink:a=0.3", "-c:a", "aac", "-b:a", "192k")
    wav = await normalize_to_wav(path.read_bytes())
    assert wav_duration_seconds(wav) == pytest.approx(60.0, abs=0.5)


@pytest.mark.parametrize(
    ("name", "codec"),
    [("a.wav", []), ("a.mp3", []), ("a.flac", []), ("a.ogg", ["-c:a", "libopus"]), ("a.webm", ["-c:a", "libopus"]),
     ("a.aac", []), ("a.mp4", ["-c:a", "aac"])],
)
async def test_every_accepted_format_decodes(tmp_path, name, codec):
    path = encode(tmp_path, name, "-f", "lavfi", "-i", "sine=frequency=220:duration=2", *codec)
    assert wav_duration_seconds(await normalize_to_wav(path.read_bytes())) == pytest.approx(2.0, abs=0.2)


async def test_file_metadata_cannot_corrupt_the_audio(tmp_path):
    source = ("-f", "lavfi", "-i", "sine=frequency=220:duration=2")
    tagged = encode(tmp_path, "tagged.flac", *source, "-metadata", "title=my data file")
    plain = encode(tmp_path, "plain.flac", *source)
    assert await normalize_to_wav(tagged.read_bytes()) == await normalize_to_wav(plain.read_bytes())


async def test_uploads_cannot_pull_in_other_files(tmp_path):
    local = encode(tmp_path, "local.wav", "-f", "lavfi", "-i", "sine=frequency=440:duration=4")
    playlist = f"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\n{local.as_uri()}\n#EXT-X-ENDLIST\n"
    concat = f"ffconcat version 1.0\nfile '{local.as_posix()}'\n"
    for upload in (playlist, concat):
        with pytest.raises(InvalidAudioError):
            await normalize_to_wav(upload.encode())


async def test_small_upload_cannot_expand_past_the_decode_limit(tmp_path):
    long_silence = encode(tmp_path, "long.webm", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-t", "1800", "-c:a", "libopus", "-b:a", "6k")
    wav = await normalize_to_wav(long_silence.read_bytes(), max_seconds=31)
    assert wav_duration_seconds(wav) == pytest.approx(31, abs=0.5)
    assert len(wav) < 2 * 1024 * 1024


async def test_normalize_converts_webm_to_mono_16k_wav():
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
