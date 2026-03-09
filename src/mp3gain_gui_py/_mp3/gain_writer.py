"""Apply or undo global_gain changes frame-by-frame.

Legacy Pointers:
- LEGACY_PTR:MP3_CHANGE_GAIN
- LEGACY_PTR:MP3_SKIP_XING_INFO
- LEGACY_PTR:MP3_TEMPFILE_REPLACE

Mirrors changeGain() from mp3gain.c.
"""

from __future__ import annotations

import os
import stat
import time
from typing import TYPE_CHECKING

from .frame_parser import (
    find_next_frame,
    global_gain_offsets,
    has_xing_or_info_tag,
    parse_frame_header,
)

if TYPE_CHECKING:
    from pathlib import Path


def _peek8_bits(data: bytearray, byte_off: int, bit_off: int) -> int:
    word = (data[byte_off] << 8) | data[byte_off + 1]
    word >>= 8 - bit_off
    return word & 0xFF


def _set8_bits(data: bytearray, byte_off: int, bit_off: int, value: int) -> None:
    """Write ``value`` (8 bits) into ``data`` at the given bit position."""
    # maskLeft[k]  keeps only the top k bits of the byte (k bits from MSB)
    mask_left  = (0xFF00 >> bit_off) & 0xFF
    # maskRight[k] keeps only the bottom (8-k) bits of the byte
    mask_right = (0xFF >> bit_off) & 0xFF

    v = (value & 0xFF) << (8 - bit_off)   # shift value into place in 16-bit word
    data[byte_off]     = (data[byte_off]     & mask_left)  | (v >> 8)
    data[byte_off + 1] = (data[byte_off + 1] & mask_right) | (v & 0xFF)


def apply_gain_change(
    path: Path,
    gain_delta: int,
    *,
    wrap: bool = False,
    preserve_timestamp: bool = False,
    gain_delta_right: int | None = None,
) -> None:
    """Modify every frame's global_gain fields by ``gain_delta``.

    Legacy pointer: LEGACY_PTR:MP3_CHANGE_GAIN.

    Args:
        path:               MP3 file to modify in-place (via temp file).
        gain_delta:         Amount to add to each global_gain byte.
        wrap:               If True, wrap around 0-255 (C wrapGain mode).
                            If False, clamp to 0-255 and skip gain==0 frames.
        preserve_timestamp: Restore file modification time after write.
        gain_delta_right:   If provided, apply a *different* gain to the right
                            channel (dual-mono mode).  gain_delta is used for
                            the left channel.
    """
    if gain_delta == 0 and (gain_delta_right is None or gain_delta_right == 0):
        return

    mtime: float | None = None
    if preserve_timestamp:
        mtime = path.stat().st_mtime

    data = bytearray(path.read_bytes())

    pos = 0
    # Skip ID3v2
    if data[:3] == b"ID3":
        id3_size = (
            (data[9] & 0x7F)
            | ((data[8] & 0x7F) << 7)
            | ((data[7] & 0x7F) << 14)
            | ((data[6] & 0x7F) << 21)
        )
        pos = 10 + id3_size

    first_audio_frame = True

    while True:
        pos = find_next_frame(bytes(data), pos)
        if pos < 0:
            break
        header = parse_frame_header(bytes(data), pos)
        if header is None:
            pos += 1
            continue
        if pos + header.frame_size_bytes > len(data):
            break

        # mp3gain.c skips the Xing/Info frame when present as first frame.
        if first_audio_frame:
            first_audio_frame = False
            if has_xing_or_info_tag(bytes(data), pos, header):
                pos += header.frame_size_bytes
                continue

        offsets = global_gain_offsets(header)

        changed = False
        for ch_idx, (byte_off, bit_off) in enumerate(offsets):
            abs_byte = pos + byte_off
            if abs_byte + 1 >= len(data):
                continue

            delta = gain_delta
            if gain_delta_right is not None and ch_idx % header.num_channels == 1:
                delta = gain_delta_right

            gain = _peek8_bits(data, abs_byte, bit_off)

            if wrap:
                new_gain = (gain + delta) & 0xFF
            else:
                if gain == 0:
                    continue  # skip silence frames
                new_gain = max(0, min(255, gain + delta))

            _set8_bits(data, abs_byte, bit_off, new_gain)
            changed = True

        # Recalculate CRC if the frame is CRC-protected and we changed something
        if changed and header.crc_protected:
            _recalc_crc(data, pos, header.mpeg_version == 0x03, header.num_channels == 1)

        pos += header.frame_size_bytes

    # Write via temp file then rename.
    tmp = _legacy_tmp_path(path)
    tmp.write_bytes(bytes(data))
    _replace_with_retry(tmp, path)

    if preserve_timestamp and mtime is not None:
        os.utime(path, (mtime, mtime))


def _recalc_crc(data: bytearray, frame_start: int, mpeg1: bool, mono: bool) -> None:
    """Recalculate and write CRC bytes [4:6] for the frame at frame_start."""
    from .crc import crc16_update

    crc = 0xFFFF
    crc = crc16_update(data[frame_start + 2], crc)
    crc = crc16_update(data[frame_start + 3], crc)
    # sideinfo starts at byte 6 of the frame
    si_len = (17 if mono else 32) if mpeg1 else (9 if mono else 17)
    for i in range(6, 6 + si_len):
        crc = crc16_update(data[frame_start + i], crc)
    data[frame_start + 4] = (crc >> 8) & 0xFF
    data[frame_start + 5] = crc & 0xFF


def _legacy_tmp_path(path: Path) -> Path:
    """Build legacy-compatible temp filename.

    Legacy pointer: LEGACY_PTR:MP3_TEMPFILE_REPLACE.
    """
    name = path.name
    if name.lower().endswith("tmp"):
        return path.with_name(name + ".TMP")
    if path.suffix:
        return path.with_suffix(".TMP")
    return path.with_name(name + ".TMP")


def _replace_with_retry(tmp: Path, target: Path, *, retries: int = 5, delay_s: float = 0.05) -> None:
    """Replace destination with bounded retries for transient Windows locks.

    Legacy pointer: LEGACY_PTR:MP3_TEMPFILE_REPLACE.
    """
    last_error: OSError | None = None
    for _attempt in range(retries):
        try:
            if target.exists():
                os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
            os.replace(tmp, target)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(delay_s)
    if last_error is not None:
        raise last_error


def undo_gain_change(
    path: Path,
    undo_tag: str,
    *,
    wrap: bool = False,
    preserve_timestamp: bool = False,
) -> None:
    """Undo a previously applied gain change using the MP3GAIN_UNDO tag value.

    Args:
        path:     MP3 file to restore.
        undo_tag: Value of the MP3GAIN_UNDO tag, e.g. ``"+006,+006,W"``.
        wrap:     As for apply_gain_change.
        preserve_timestamp: As for apply_gain_change.
    """
    parts = undo_tag.strip().split(",")
    if len(parts) != 3:
        raise ValueError(f"Invalid MP3GAIN_UNDO tag value: {undo_tag!r}")

    left_delta = -int(parts[0])    # negate to undo
    right_delta = -int(parts[1])
    # parts[2] is 'W' or 'N' — wrap mode is passed via the wrap param

    apply_gain_change(
        path,
        left_delta,
        wrap=wrap,
        preserve_timestamp=preserve_timestamp,
        gain_delta_right=right_delta,
    )
