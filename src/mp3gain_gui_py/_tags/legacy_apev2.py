"""Legacy-style APEv2 MP3Gain tag read/write helpers.

Legacy Pointers:
- LEGACY_PTR:TAGS_APEV2_WRITE
- LEGACY_PTR:TAGS_DELETE_KEYS
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .formats import (
    ALL_MP3GAIN_KEYS,
    TAG_ALBUM_GAIN,
    TAG_ALBUM_PEAK,
    TAG_MP3GAIN_ALBUM_MINMAX,
    TAG_MP3GAIN_MINMAX,
    TAG_MP3GAIN_UNDO,
    TAG_TRACK_GAIN,
    TAG_TRACK_PEAK,
    format_gain,
    format_minmax,
    format_peak,
    format_undo,
)
from .reader import TagData

if TYPE_CHECKING:
    from pathlib import Path

_APE_ID = b"APETAGEX"
_APE_STRUCT_SIZE = 32
_APE_VERSION = 2000
_APE_FLAG_HAS_HEADER = 1 << 31
_APE_FLAG_THIS_IS_HEADER = 1 << 29
_APE_MP3GAIN_ORDER = (
    TAG_MP3GAIN_MINMAX,
    TAG_MP3GAIN_ALBUM_MINMAX,
    TAG_MP3GAIN_UNDO,
    TAG_TRACK_GAIN,
    TAG_TRACK_PEAK,
    TAG_ALBUM_GAIN,
    TAG_ALBUM_PEAK,
)


@dataclass(frozen=True)
class _ParsedApeInfo:
    base_end: int
    trailer_start: int
    other_fields: bytes
    other_count: int


def write_legacy_apev2_tags(path: Path, data: TagData) -> None:
    """Write/update MP3Gain APEv2 fields while preserving non-MP3Gain fields.

    Legacy pointer: LEGACY_PTR:TAGS_APEV2_WRITE.
    """
    payload = path.read_bytes()
    parsed = _parse_existing_ape(payload)
    if parsed is None:
        trailer_start = _find_trailer_start(payload)
        parsed = _ParsedApeInfo(
            base_end=trailer_start,
            trailer_start=trailer_start,
            other_fields=b"",
            other_count=0,
        )

    mp3gain_fields = _build_mp3gain_fields(data)
    field_blob = parsed.other_fields + mp3gain_fields
    field_count = parsed.other_count + _count_fields(mp3gain_fields)

    if field_count > 0:
        ape_bytes = _build_ape_tag_bytes(field_blob, field_count)
    else:
        ape_bytes = b""

    new_payload = (
        payload[: parsed.base_end] + ape_bytes + payload[parsed.trailer_start :]
    )
    _atomic_write(path, new_payload)


def delete_legacy_apev2_keys(path: Path) -> None:
    """Delete only MP3Gain-owned APEv2 keys.

    Legacy pointer: LEGACY_PTR:TAGS_DELETE_KEYS.
    """
    write_legacy_apev2_tags(path, TagData(tag_format="apev2"))


def _atomic_write(path: Path, payload: bytes) -> None:
    tmp = _legacy_tmp_path(path)
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def _legacy_tmp_path(path: Path) -> Path:
    name = path.name
    if name.lower().endswith("tmp"):
        return path.with_name(name + ".TMP")
    if path.suffix:
        return path.with_suffix(".TMP")
    return path.with_name(name + ".TMP")


def _build_mp3gain_fields(data: TagData) -> bytes:
    kv: dict[str, str] = {}
    if data.min_gain is not None and data.max_gain is not None:
        kv[TAG_MP3GAIN_MINMAX] = format_minmax(data.min_gain, data.max_gain)
    if data.album_min_gain is not None and data.album_max_gain is not None:
        kv[TAG_MP3GAIN_ALBUM_MINMAX] = format_minmax(
            data.album_min_gain, data.album_max_gain
        )
    if (
        data.undo_left is not None
        and data.undo_right is not None
        and data.undo_mode is not None
    ):
        kv[TAG_MP3GAIN_UNDO] = format_undo(
            data.undo_left, data.undo_right, data.undo_mode
        )
    if data.track_gain_db is not None:
        kv[TAG_TRACK_GAIN] = format_gain(data.track_gain_db)
    if data.track_peak is not None:
        kv[TAG_TRACK_PEAK] = format_peak(data.track_peak)
    if data.album_gain_db is not None:
        kv[TAG_ALBUM_GAIN] = format_gain(data.album_gain_db)
    if data.album_peak is not None:
        kv[TAG_ALBUM_PEAK] = format_peak(data.album_peak)

    parts: list[bytes] = []
    for key in _APE_MP3GAIN_ORDER:
        value = kv.get(key)
        if value is None:
            continue
        parts.append(_build_field(key, value))
    return b"".join(parts)


def _build_field(name: str, value: str) -> bytes:
    name_bytes = name.encode("ascii")
    value_bytes = value.encode("ascii")
    out = bytearray()
    out.extend(len(value_bytes).to_bytes(4, "little"))
    out.extend((0).to_bytes(4, "little"))
    out.extend(name_bytes)
    out.append(0)
    out.extend(value_bytes)
    return bytes(out)


def _count_fields(blob: bytes) -> int:
    count = 0
    pos = 0
    total = len(blob)
    while pos + 8 <= total:
        value_size = int.from_bytes(blob[pos : pos + 4], "little")
        name_end = blob.find(b"\x00", pos + 8)
        if name_end < 0:
            break
        value_start = name_end + 1
        value_end = value_start + value_size
        if value_end > total:
            break
        count += 1
        pos = value_end
    return count


def _build_ape_tag_bytes(field_blob: bytes, field_count: int) -> bytes:
    length_without_header = len(field_blob) + _APE_STRUCT_SIZE
    header = _build_ape_struct(
        version=_APE_VERSION,
        length=length_without_header,
        count=field_count,
        flags=_APE_FLAG_HAS_HEADER | _APE_FLAG_THIS_IS_HEADER,
    )
    footer = _build_ape_struct(
        version=_APE_VERSION,
        length=length_without_header,
        count=field_count,
        flags=_APE_FLAG_HAS_HEADER,
    )
    return header + field_blob + footer


def _build_ape_struct(*, version: int, length: int, count: int, flags: int) -> bytes:
    out = bytearray()
    out.extend(_APE_ID)
    out.extend(version.to_bytes(4, "little"))
    out.extend(length.to_bytes(4, "little"))
    out.extend(count.to_bytes(4, "little"))
    out.extend(flags.to_bytes(4, "little"))
    out.extend(b"\x00" * 8)
    return bytes(out)


def _parse_existing_ape(data: bytes) -> _ParsedApeInfo | None:
    trailer_start = _find_trailer_start(data)
    if trailer_start < _APE_STRUCT_SIZE:
        return None

    footer_start = trailer_start - _APE_STRUCT_SIZE
    footer = data[footer_start:trailer_start]
    if footer[:8] != _APE_ID:
        return None

    version = int.from_bytes(footer[8:12], "little")
    tag_length = int.from_bytes(footer[12:16], "little")
    flags = int.from_bytes(footer[20:24], "little")
    if version not in {1000, 2000}:
        return None
    if tag_length < _APE_STRUCT_SIZE or tag_length > trailer_start:
        return None

    fields_start = trailer_start - tag_length
    fields_end = footer_start
    if fields_start < 0 or fields_end < fields_start:
        return None

    header_start = fields_start - _APE_STRUCT_SIZE
    has_header = bool(flags & _APE_FLAG_HAS_HEADER)
    if has_header:
        if header_start < 0:
            return None
        header = data[header_start:fields_start]
        if header[:8] != _APE_ID:
            return None
        base_end = header_start
    else:
        base_end = fields_start

    other_fields, other_count = _extract_other_fields(data[fields_start:fields_end])
    return _ParsedApeInfo(
        base_end=base_end,
        trailer_start=trailer_start,
        other_fields=other_fields,
        other_count=other_count,
    )


def _extract_other_fields(field_blob: bytes) -> tuple[bytes, int]:
    out_parts: list[bytes] = []
    count = 0
    pos = 0
    total = len(field_blob)
    while pos + 8 <= total:
        value_size = int.from_bytes(field_blob[pos : pos + 4], "little")
        name_start = pos + 8
        name_end = field_blob.find(b"\x00", name_start)
        if name_end < 0:
            break
        value_start = name_end + 1
        value_end = value_start + value_size
        if value_end > total:
            break
        name = field_blob[name_start:name_end].decode("latin-1", errors="ignore")
        raw_field = field_blob[pos:value_end]
        if name.upper() not in ALL_MP3GAIN_KEYS:
            out_parts.append(raw_field)
            count += 1
        pos = value_end
    return b"".join(out_parts), count


def _find_trailer_start(data: bytes) -> int:
    pos = len(data)
    while True:
        old = pos
        if pos >= 128 and data[pos - 128 : pos - 125] == b"TAG":
            pos -= 128
            continue
        if pos >= 15:
            footer = data[pos - 15 : pos]
            if footer[6:15] == b"LYRICS200" and footer[:6].isdigit():
                lyrics_len = int(footer[:6])
                start = pos - 15 - lyrics_len
                if start >= 0 and data[start : start + 11] == b"LYRICSBEGIN":
                    pos = start
                    continue
        if pos == old:
            break
    return pos
