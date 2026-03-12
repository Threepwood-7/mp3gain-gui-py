"""PCM chunk reader using miniaudio for float32 stereo chunks."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import array
    from collections.abc import Callable, Iterator
    from pathlib import Path


def read_mp3_info(path: Path | str) -> tuple[int, int]:
    """Return ``(sample_rate, num_channels)`` from MP3 file metadata."""
    import miniaudio  # type: ignore[import-untyped]

    info = miniaudio.get_file_info(str(path))
    return int(info.sample_rate), int(info.nchannels)


def iter_pcm_chunks(
    path: Path | str,
    chunk_frames: int = 4096,
) -> Iterator[tuple[int, int, array.array[float]]]:
    """Yield ``(sample_rate, num_channels, samples)`` blocks."""
    import miniaudio  # type: ignore[import-untyped]

    sample_rate, _nch = read_mp3_info(path)

    stream_file = cast(
        "Callable[..., Iterator[array.array[float]]]",
        miniaudio.stream_file,
    )
    for samples in stream_file(
        str(path),
        output_format=miniaudio.SampleFormat.FLOAT32,
        nchannels=2,
        sample_rate=sample_rate,
        frames_to_read=chunk_frames,
    ):
        yield sample_rate, 2, samples


def decode_to_stereo_chunks(
    path: Path | str,
    chunk_frames: int = 4096,
) -> Iterator[tuple[int, list[float], list[float]]]:
    """Yield ``(sample_rate, left, right)`` de-interleaved float lists."""
    for sample_rate, _nc, samples in iter_pcm_chunks(path, chunk_frames):
        # GainAnalyzer expects PCM-16 scale (-32768..32767), same as the C reference.
        # miniaudio yields normalized float32 (-1..1), so scale up.
        left: list[float] = [v * 32768.0 for v in samples[0::2]]
        right: list[float] = [v * 32768.0 for v in samples[1::2]]
        yield sample_rate, left, right
