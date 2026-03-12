"""Read MP3Gain tags from APEv2 or ID3v2 frames.

Legacy Pointers:
- LEGACY_PTR:TAGS_APEV2_READ
- LEGACY_PTR:TAGS_ID3_READ
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

from .formats import (
    TAG_ALBUM_GAIN,
    TAG_ALBUM_PEAK,
    TAG_MP3GAIN_ALBUM_MINMAX,
    TAG_MP3GAIN_MINMAX,
    TAG_MP3GAIN_UNDO,
    TAG_TRACK_GAIN,
    TAG_TRACK_PEAK,
    parse_gain,
    parse_minmax,
    parse_peak,
    parse_undo,
)


@dataclass
class TagData:
    """All MP3Gain-related tag fields for one file."""

    tag_format: Literal["apev2", "id3", "none"] = "none"

    track_gain_db: float | None = None
    track_peak: float | None = None
    album_gain_db: float | None = None
    album_peak: float | None = None

    undo_left: int | None = None
    undo_right: int | None = None
    undo_mode: str | None = None  # 'W' or 'N'

    min_gain: int | None = None
    max_gain: int | None = None
    album_min_gain: int | None = None
    album_max_gain: int | None = None

    extra: dict[str, str] = field(default_factory=dict)

    # ── Derived helpers ──────────────────────────────────────────────────

    @property
    def has_undo(self) -> bool:
        return self.undo_left is not None

    @property
    def undo_tag_value(self) -> str:
        """Reconstruct the raw MP3GAIN_UNDO string."""
        if self.undo_left is None or self.undo_right is None or self.undo_mode is None:
            return ""
        return f"{self.undo_left:+04d},{self.undo_right:+04d},{self.undo_mode}"


def read_tags(path: Path) -> TagData:
    """Read MP3Gain tags from *path*, preferring APEv2 over ID3v2.

    Legacy pointers: LEGACY_PTR:TAGS_APEV2_READ, LEGACY_PTR:TAGS_ID3_READ.

    Returns a :class:`TagData` with ``tag_format="none"`` if no tags are found.
    """
    # Try APEv2 first
    result = _read_apev2(path)
    if result is not None:
        return result

    # Fall back to ID3v2 TXXX frames
    result = _read_id3(path)
    if result is not None:
        return result

    return TagData(tag_format="none")


# ── Internal helpers ───────────────────────────────────────────────────────────


def _read_apev2(path: Path) -> TagData | None:
    try:
        import mutagen.apev2 as _apev2  # type: ignore[import-untyped]

        tags = _apev2.APEv2(str(path))
    except Exception:
        return None

    data = TagData(tag_format="apev2")
    _fill_from_dict({k.upper(): str(v) for k, v in tags.items()}, data)
    return data


def _read_id3(path: Path) -> TagData | None:
    try:
        import mutagen.id3 as _id3  # type: ignore[import-untyped]

        tags = _id3.ID3(str(path))
    except Exception:
        return None

    # Collect TXXX frames
    raw: dict[str, str] = {}
    for key, frame in tags.items():
        if key.startswith("TXXX:"):
            desc = key[5:].upper()
            raw[desc] = str(frame.text[0]) if frame.text else ""

    if not raw:
        return None

    data = TagData(tag_format="id3")
    _fill_from_dict(raw, data)
    return data


def _fill_from_dict(raw: dict[str, str], data: TagData) -> None:
    """Populate *data* from a normalized (upper-case keys) dict."""
    if v := raw.get(TAG_TRACK_GAIN):
        data.track_gain_db = parse_gain(v)
    if v := raw.get(TAG_TRACK_PEAK):
        data.track_peak = parse_peak(v)
    if v := raw.get(TAG_ALBUM_GAIN):
        data.album_gain_db = parse_gain(v)
    if v := raw.get(TAG_ALBUM_PEAK):
        data.album_peak = parse_peak(v)
    if v := raw.get(TAG_MP3GAIN_UNDO):
        parsed_undo = parse_undo(v)
        if parsed_undo is not None:
            data.undo_left, data.undo_right, data.undo_mode = parsed_undo
    if v := raw.get(TAG_MP3GAIN_MINMAX):
        parsed_mm = parse_minmax(v)
        if parsed_mm is not None:
            data.min_gain, data.max_gain = parsed_mm
    if v := raw.get(TAG_MP3GAIN_ALBUM_MINMAX):
        parsed_amm = parse_minmax(v)
        if parsed_amm is not None:
            data.album_min_gain, data.album_max_gain = parsed_amm
