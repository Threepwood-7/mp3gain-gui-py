"""PCM chunk reader using miniaudio — decodes MP3 → float32 stereo chunks.

miniaudio.stream_file yields plain array.array objects of interleaved float32
samples.  Sample rate and channel count come from miniaudio.get_file_info.
"""

from __future__ import annotations

import array
from collections.abc import Iterator
from pathlib import Path


def read_mp3_info(path: Path | str) -> tuple[int, int]:
    """Return ``(sample_rate, num_channels)`` from MP3 file metadata.

    Uses miniaudio.get_file_info for a fast header-only read.
    """
    import miniaudio  # type: ignore[import-untyped]

    info = miniaudio.get_file_info(str(path))
    return int(info.sample_rate), int(info.nchannels)


def iter_pcm_chunks(
    path: Path | str,
    chunk_frames: int = 4096,
) -> Iterator[tuple[int, int, array.array[float]]]:
    """Yield ``(sample_rate, num_channels, samples)`` blocks.

    ``samples`` is an interleaved float32 ``array.array``; always 2 channels.
    """
    import miniaudio  # type: ignore[import-untyped]

    sample_rate, _nch = read_mp3_info(path)

    for block in miniaudio.stream_file(
        str(path),
        output_format=miniaudio.SampleFormat.FLOAT32,
        nchannels=2,
        sample_rate=sample_rate,
        frames_to_read=chunk_frames,
    ):
        samples: array.array[float] = block  # type: ignore[assignment]
        yield sample_rate, 2, samples


def decode_to_stereo_chunks(
    path: Path | str,
    chunk_frames: int = 4096,
) -> Iterator[tuple[int, list[float], list[float]]]:
    """Yield ``(sample_rate, left, right)`` de-interleaved float lists.

    Both ``left`` and ``right`` have up to ``chunk_frames`` values per chunk.
    """
    for sample_rate, _nc, samples in iter_pcm_chunks(path, chunk_frames):
        # GainAnalyzer expects PCM-16 scale (–32768..32767), same as the C
        # reference.  miniaudio yields normalised float32 (–1..1), so scale up.
        left: list[float] = [v * 32768.0 for v in samples[0::2]]
        right: list[float] = [v * 32768.0 for v in samples[1::2]]
        yield sample_rate, left, right
