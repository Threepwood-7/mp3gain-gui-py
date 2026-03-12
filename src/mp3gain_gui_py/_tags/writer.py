"""Write or delete MP3Gain tags using mutagen.

Legacy Pointers:
- LEGACY_PTR:TAGS_APEV2_WRITE
- LEGACY_PTR:TAGS_ID3_WRITE
- LEGACY_PTR:TAGS_DELETE_KEYS
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

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
from .legacy_apev2 import delete_legacy_apev2_keys, write_legacy_apev2_tags

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from .reader import TagData


def write_tags(
    path: Path,
    data: TagData,
    *,
    tag_format: Literal["apev2", "id3"] = "apev2",
) -> None:
    """Write all populated fields from *data* to *path*.

    Legacy pointer: LEGACY_PTR:TAGS_APEV2_WRITE.

    Existing MP3Gain keys are replaced; other tags are preserved.
    """
    if tag_format == "apev2":
        _write_apev2(path, data)
    else:
        _write_id3(path, data)


def delete_tags(path: Path) -> None:
    """Remove all MP3Gain tag fields from *path* (both APEv2 and ID3v2).

    Legacy pointer: LEGACY_PTR:TAGS_DELETE_KEYS.
    """
    _delete_apev2_keys(path)
    _delete_id3_keys(path)


def delete_tags_for_format(path: Path, *, tag_format: Literal["apev2", "id3"]) -> None:
    """Remove MP3Gain fields from the selected backend only."""
    if tag_format == "apev2":
        _delete_apev2_keys(path)
    else:
        _delete_id3_keys(path)


# ── APEv2 ──────────────────────────────────────────────────────────────────────


def _write_apev2(path: Path, data: TagData) -> None:
    write_legacy_apev2_tags(path, data)


def _delete_apev2_keys(path: Path) -> None:
    delete_legacy_apev2_keys(path)


# ── ID3v2 ──────────────────────────────────────────────────────────────────────


def _write_id3(path: Path, data: TagData) -> None:
    """Write MP3Gain keys to ID3v2 TXXX frames.

    Legacy pointer: LEGACY_PTR:TAGS_ID3_WRITE.
    """
    import mutagen.id3 as _id3  # type: ignore[import-untyped]

    try:
        tags = _id3.ID3(str(path))
    except Exception:
        tags = _id3.ID3()

    kv = _build_kv(data)
    txxx_frame = cast("type[Any]", _id3.Frames["TXXX"])
    for key, value in kv.items():
        frame_key = f"TXXX:{key}"
        tags[frame_key] = txxx_frame(encoding=3, desc=key, text=[value])

    cast("Any", tags).save(str(path))


def _delete_id3_keys(path: Path) -> None:
    try:
        import mutagen.id3 as _id3  # type: ignore[import-untyped]

        tags = _id3.ID3(str(path))
        changed = False
        tag_keys = list(cast("Iterable[object]", tags.keys()))
        for raw_key in tag_keys:
            key = str(raw_key)
            if key.startswith("TXXX:"):
                desc = key[5:].upper()
                if desc in ALL_MP3GAIN_KEYS:
                    del tags[key]
                    changed = True
        if changed:
            cast("Any", tags).save(str(path))
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
    if (
        data.undo_left is not None
        and data.undo_right is not None
        and data.undo_mode is not None
    ):
        kv[TAG_MP3GAIN_UNDO] = format_undo(
            data.undo_left, data.undo_right, data.undo_mode
        )
    if data.min_gain is not None and data.max_gain is not None:
        kv[TAG_MP3GAIN_MINMAX] = format_minmax(data.min_gain, data.max_gain)
    if data.album_min_gain is not None and data.album_max_gain is not None:
        kv[TAG_MP3GAIN_ALBUM_MINMAX] = format_minmax(
            data.album_min_gain, data.album_max_gain
        )

    return kv
