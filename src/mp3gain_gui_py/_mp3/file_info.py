"""Scan an MP3 file to collect min/max global_gain and max amplitude."""

from __future__ import annotations

from pathlib import Path

from .frame_parser import find_next_frame, global_gain_offsets, parse_frame_header


def _peek8_bits(data: bytes, byte_off: int, bit_off: int) -> int:
    """Read 8 bits from ``data`` starting at bit position ``(byte_off, bit_off)``."""
    word = (data[byte_off] << 8) | data[byte_off + 1]
    word >>= 8 - bit_off
    return word & 0xFF


def scan_file(path: Path) -> tuple[int, int]:
    """Return ``(min_global_gain, max_global_gain)`` across all frames.

    Mirrors scanFrameGain() from mp3gain.c.
    """
    data = path.read_bytes()
    min_gain = 255
    max_gain = 0
    pos = 0

    # Skip ID3v2 tag if present
    if data[:3] == b"ID3":
        id3_size = (
            (data[9] & 0x7F)
            | ((data[8] & 0x7F) << 7)
            | ((data[7] & 0x7F) << 14)
            | ((data[6] & 0x7F) << 21)
        )
        pos = 10 + id3_size

    while True:
        pos = find_next_frame(data, pos)
        if pos < 0:
            break
        header = parse_frame_header(data, pos)
        if header is None:
            pos += 1
            continue

        if pos + header.frame_size_bytes > len(data):
            break

        for byte_off, bit_off in global_gain_offsets(header):
            abs_byte = pos + byte_off
            if abs_byte + 1 >= len(data):
                continue
            gain = _peek8_bits(data, abs_byte, bit_off)
            if gain < min_gain:
                min_gain = gain
            if gain > max_gain:
                max_gain = gain

        pos += header.frame_size_bytes

    if min_gain > max_gain:
        return 0, 0
    return min_gain, max_gain


def scan_max_amplitude(path: Path) -> float:
    """Return maximum decoded sample amplitude (0.0 .. 32768.0+ scale).

    Uses miniaudio to decode; scans all samples for the absolute peak.
    The value is in the same scale as mp3gain's "Max Amplitude" column
    (i.e. raw 16-bit integer equivalent = float32 * 32768).
    """
    from .._engine.pcm_reader import iter_pcm_chunks

    peak = 0.0
    for _sr, _nc, samples in iter_pcm_chunks(path):
        for s in samples:
            av = abs(s)
            if av > peak:
                peak = av
    return peak * 32768.0
