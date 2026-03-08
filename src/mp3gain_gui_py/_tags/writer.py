"""Write or delete MP3Gain tags using mutagen."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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


def write_tags(
    path: Path,
    data: TagData,
    *,
    tag_format: Literal["apev2", "id3"] = "apev2",
) -> None:
    """Write all populated fields from *data* to *path*.

    Existing MP3Gain keys are replaced; other tags are preserved.
    """
    if tag_format == "apev2":
        _write_apev2(path, data)
    else:
        _write_id3(path, data)


def delete_tags(path: Path) -> None:
    """Remove all MP3Gain tag fields from *path* (both APEv2 and ID3v2)."""
    _delete_apev2_keys(path)
    _delete_id3_keys(path)


# ── APEv2 ──────────────────────────────────────────────────────────────────────


def _write_apev2(path: Path, data: TagData) -> None:
    import mutagen.apev2 as _apev2  # type: ignore[import-untyped]

    try:
        tags = _apev2.APEv2(str(path))
    except Exception:
        tags = _apev2.APEv2()

    kv = _build_kv(data)
    for key, value in kv.items():
        tags[key] = value

    tags.save(str(path))


def _delete_apev2_keys(path: Path) -> None:
    try:
        import mutagen.apev2 as _apev2  # type: ignore[import-untyped]
        tags = _apev2.APEv2(str(path))
        changed = False
        for key in list(tags.keys()):
            if key.upper() in ALL_MP3GAIN_KEYS:
                del tags[key]
                changed = True
        if changed:
            tags.save(str(path))
    except Exception:
        pass


# ── ID3v2 ──────────────────────────────────────────────────────────────────────


def _write_id3(path: Path, data: TagData) -> None:
    import mutagen.id3 as _id3  # type: ignore[import-untyped]

    try:
        tags = _id3.ID3(str(path))
    except Exception:
        tags = _id3.ID3()

    kv = _build_kv(data)
    for key, value in kv.items():
        frame_key = f"TXXX:{key}"
        tags[frame_key] = _id3.TXXX(encoding=3, desc=key, text=[value])

    tags.save(str(path))


def _delete_id3_keys(path: Path) -> None:
    try:
        import mutagen.id3 as _id3  # type: ignore[import-untyped]
        tags = _id3.ID3(str(path))
        changed = False
        for key in list(tags.keys()):
            if key.startswith("TXXX:"):
                desc = key[5:].upper()
                if desc in ALL_MP3GAIN_KEYS:
                    del tags[key]
                    changed = True
        if changed:
            tags.save(str(path))
    except Exception:
        pass


# ── Shared builder ─────────────────────────────────────────────────────────────


def _build_kv(data: TagData) -> dict[str, str]:
    kv: dict[str, str] = {}

    if data.track_gain_db is not None:
        kv[TAG_TRACK_GAIN] = format_gain(data.track_gain_db)
    if data.track_peak is not None:
        kv[TAG_TRACK_PEAK] = format_peak(data.track_peak)
    if data.album_gain_db is not None:
        kv[TAG_ALBUM_GAIN] = format_gain(data.album_gain_db)
    if data.album_peak is not None:
        kv[TAG_ALBUM_PEAK] = format_peak(data.album_peak)
    if data.undo_left is not None and data.undo_right is not None and data.undo_mode is not None:
        kv[TAG_MP3GAIN_UNDO] = format_undo(data.undo_left, data.undo_right, data.undo_mode)
    if data.min_gain is not None and data.max_gain is not None:
        kv[TAG_MP3GAIN_MINMAX] = format_minmax(data.min_gain, data.max_gain)
    if data.album_min_gain is not None and data.album_max_gain is not None:
        kv[TAG_MP3GAIN_ALBUM_MINMAX] = format_minmax(data.album_min_gain, data.album_max_gain)

    return kv
