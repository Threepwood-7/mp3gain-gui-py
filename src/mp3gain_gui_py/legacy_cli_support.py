"""Output and tag-state helpers for the legacy-compatible CLI."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

from ._legacy_exact import db_to_legacy_steps
from ._tags.reader import TagData

if TYPE_CHECKING:
    from pathlib import Path

    from ._legacy_exact import LegacyExactProcessor


def format_table_line(
    path: Path | str,
    *,
    steps: int,
    db_gain: float,
    max_amp: float,
    min_gain: int,
    max_gain: int,
    album_steps: int | None = None,
    album_db_gain: float | None = None,
    album_max_amp: float | None = None,
    album_min_gain: int | None = None,
    album_max_gain: int | None = None,
) -> str:
    fields = [
        str(path),
        str(steps),
        f"{db_gain:.6f}",
        f"{max_amp:.6f}",
        str(max_gain),
        str(min_gain),
    ]
    if (
        album_steps is not None
        and album_db_gain is not None
        and album_max_amp is not None
        and album_min_gain is not None
        and album_max_gain is not None
    ):
        fields.extend(
            [
                str(album_steps),
                f"{album_db_gain:.6f}",
                f"{album_max_amp:.6f}",
                str(album_max_gain),
                str(album_min_gain),
            ]
        )
    return "\t".join(fields)


def print_info(
    mode: Literal["none", "version", "help", "help_qmark"], topic: str
) -> None:
    if mode == "version":
        print("mp3gain-gui-py legacy_cli parity mode (target baseline: 89 dB)")
        return
    if mode in {"help", "help_qmark"}:
        print("Usage: legacy_cli [switches] file1.mp3 [file2.mp3 ...]")
        print(
            "Switches: /v /h /? /g /l /r /k /a /m /d /c /o /t /q /p /x /f /s /u /w /e"
        )
        if topic:
            print(f"Help topic: {topic}")


def load_runtime_tags(
    processor: LegacyExactProcessor,
    path: Path,
    *,
    tag_format: Literal["apev2", "id3"],
) -> TagData:
    tags = processor.read_replaygain_tags(path)
    if tag_format == "apev2" and tags.tag_format == "id3":
        return TagData(tag_format="none")
    return tags


def clear_recalc_fields(tags: TagData) -> bool:
    changed = False
    for field_name in (
        "track_gain_db",
        "track_peak",
        "album_gain_db",
        "album_peak",
        "min_gain",
        "max_gain",
        "album_min_gain",
        "album_max_gain",
    ):
        if getattr(tags, field_name) is not None:
            setattr(tags, field_name, None)
            changed = True
    return changed


def update_track_tags_from_analysis(
    tags: TagData,
    *,
    raw_gain_db: float,
    max_amp: float,
    min_gain: int,
    max_gain: int,
    max_amp_only: bool,
) -> bool:
    changed = False
    if not max_amp_only and (
        tags.track_gain_db is None or abs(raw_gain_db - tags.track_gain_db) >= 0.01
    ):
        tags.track_gain_db = raw_gain_db
        changed = True

    peak = max_amp / 32768.0
    if tags.track_peak is None or abs(max_amp - (tags.track_peak * 32768.0)) >= 3.3:
        tags.track_peak = peak
        changed = True

    if tags.min_gain != min_gain or tags.max_gain != max_gain:
        tags.min_gain = min_gain
        tags.max_gain = max_gain
        changed = True
    return changed


def update_album_tags_from_analysis(
    tags: TagData,
    *,
    album_gain_db: float,
    album_max_amp: float,
    album_min_gain: int,
    album_max_gain: int,
    max_amp_only: bool,
) -> bool:
    changed = False
    if not max_amp_only and (
        tags.album_gain_db is None or abs(album_gain_db - tags.album_gain_db) >= 0.01
    ):
        tags.album_gain_db = album_gain_db
        changed = True

    album_peak = album_max_amp / 32768.0
    if tags.album_peak is None or abs(album_peak - tags.album_peak) >= 0.0001:
        tags.album_peak = album_peak
        changed = True

    if tags.album_min_gain != album_min_gain or tags.album_max_gain != album_max_gain:
        tags.album_min_gain = album_min_gain
        tags.album_max_gain = album_max_gain
        changed = True
    return changed


def _clamp_gain_byte(value: int) -> int:
    if value < 0:
        return 0
    if value > 255:
        return 255
    return value


def apply_gain_and_update_tags(
    tags: TagData,
    *,
    left_gain_change: int,
    right_gain_change: int,
    wrap_gain: bool,
) -> None:
    if left_gain_change == 0 and right_gain_change == 0:
        return

    undo_left = tags.undo_left or 0
    undo_right = tags.undo_right or 0
    tags.undo_left = undo_left - left_gain_change
    tags.undo_right = undo_right - right_gain_change
    tags.undo_mode = "W" if wrap_gain else "N"

    if left_gain_change != right_gain_change:
        return

    dbl_gain_change = left_gain_change * 1.505
    peak_scale = math.pow(2.0, float(left_gain_change) / 4.0)

    if tags.track_gain_db is not None:
        tags.track_gain_db -= dbl_gain_change
    if tags.track_peak is not None:
        tags.track_peak *= peak_scale
    if tags.album_gain_db is not None:
        tags.album_gain_db -= dbl_gain_change
    if tags.album_peak is not None:
        tags.album_peak *= peak_scale

    if tags.min_gain is not None and tags.max_gain is not None:
        cur_min = tags.min_gain + left_gain_change
        cur_max = tags.max_gain + left_gain_change
        if wrap_gain and (cur_min < 0 or cur_min > 255 or cur_max < 0 or cur_max > 255):
            tags.min_gain = None
            tags.max_gain = None
        elif not wrap_gain:
            tags.min_gain = 0 if tags.min_gain == 0 else _clamp_gain_byte(cur_min)
            tags.max_gain = _clamp_gain_byte(cur_max)

    if tags.album_min_gain is not None and tags.album_max_gain is not None:
        cur_min = tags.album_min_gain + left_gain_change
        cur_max = tags.album_max_gain + left_gain_change
        if wrap_gain and (cur_min < 0 or cur_min > 255 or cur_max < 0 or cur_max > 255):
            tags.album_min_gain = None
            tags.album_max_gain = None
        elif not wrap_gain:
            tags.album_min_gain = (
                0 if tags.album_min_gain == 0 else _clamp_gain_byte(cur_min)
            )
            tags.album_max_gain = _clamp_gain_byte(cur_max)


def write_runtime_tags(
    processor: LegacyExactProcessor,
    path: Path,
    tags: TagData,
    *,
    tag_format: Literal["apev2", "id3"],
    preserve_timestamp: bool,
) -> None:
    processor.write_replaygain_tagdata(
        path,
        tags,
        tag_format=tag_format,
        preserve_timestamp=preserve_timestamp,
    )


def max_no_clip_steps(max_amp: float) -> int | None:
    if max_amp <= 0.0:
        return None
    return math.floor(4.0 * math.log10(32767.0 / max_amp) / math.log10(2.0))


def would_clip(max_amp: float, gain_steps: int) -> bool:
    return max_amp * math.pow(2.0, float(gain_steps) / 4.0) > 32767.0


def _format_check_only_value_int(value: int | None) -> str:
    return "NA" if value is None else str(value)


def _format_check_only_value_float(value: float | None) -> str:
    return "NA" if value is None else f"{value:.6f}"


def format_check_only_table_line(path: Path, tags: TagData) -> str:
    track_steps = (
        str(db_to_legacy_steps(tags.track_gain_db, mp3_gain_mod=0))
        if tags.track_gain_db is not None
        else "NA"
    )
    track_db = _format_check_only_value_float(tags.track_gain_db)
    track_amp = _format_check_only_value_float(
        tags.track_peak * 32768.0 if tags.track_peak is not None else None
    )
    max_gain = _format_check_only_value_int(tags.max_gain)
    min_gain = _format_check_only_value_int(tags.min_gain)

    album_steps = (
        str(db_to_legacy_steps(tags.album_gain_db, mp3_gain_mod=0))
        if tags.album_gain_db is not None
        else "NA"
    )
    album_db = _format_check_only_value_float(tags.album_gain_db)
    album_amp = _format_check_only_value_float(
        tags.album_peak * 32768.0 if tags.album_peak is not None else None
    )
    album_max = _format_check_only_value_int(tags.album_max_gain)
    album_min = _format_check_only_value_int(tags.album_min_gain)

    return "\t".join(
        [
            str(path),
            track_steps,
            track_db,
            track_amp,
            max_gain,
            min_gain,
            album_steps,
            album_db,
            album_amp,
            album_max,
            album_min,
        ]
    )
