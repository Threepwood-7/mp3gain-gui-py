"""Process-pool task functions for worker operations."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal, cast

from .._legacy_exact.math import db_to_legacy_steps
from .._legacy_exact.processor import LegacyCompatOptions, LegacyExactProcessor
from .._tags.reader import read_tags
from .types import FileResult, StoredTagPolicy

_processor_instance: LegacyExactProcessor | None = None
_LEGACY_TARGET_DB = 89.0


def _get_processor() -> LegacyExactProcessor:
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = LegacyExactProcessor()
    return _processor_instance


def _db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def _target_offset_steps(target_db: float) -> int:
    return db_to_legacy_steps(target_db - _LEGACY_TARGET_DB)


def _analyze_track_from_tags(
    path: Path,
    *,
    target_db: float,
    allow_empty: bool,
) -> FileResult | None:
    try:
        tags = read_tags(path)
    except Exception as exc:
        return FileResult(path=path, ok=False, error_msg=str(exc))

    if allow_empty and tags.tag_format == "none":
        return None

    track_gain = tags.track_gain_db if tags.track_gain_db is not None else 0.0
    max_amp = (tags.track_peak or 0.0) * 32768.0
    min_g = tags.min_gain if tags.min_gain is not None else 0
    max_g = tags.max_gain if tags.max_gain is not None else 0
    volume_db = target_db - track_gain
    clip_track = max_amp * _db_to_linear(track_gain) if max_amp else None
    clipping = clip_track is not None and clip_track > 32767.0

    return FileResult(
        path=path,
        ok=True,
        volume_db=volume_db,
        track_gain_db=track_gain,
        max_amplitude=max_amp,
        min_gain_field=min_g,
        max_gain_field=max_g,
        clipping=clipping,
        clip_track=clip_track,
    )


def analyze_file_task(
    path_text: str,
    *,
    target_db: float,
    max_amp_only: bool,
    stored_tag_policy: StoredTagPolicy,
) -> FileResult:
    path = Path(path_text)
    if stored_tag_policy == "check_only":
        tagged = _analyze_track_from_tags(path, target_db=target_db, allow_empty=False)
        if tagged is not None:
            return tagged
        return FileResult(path=path, ok=True, volume_db=target_db, track_gain_db=0.0)
    if stored_tag_policy == "auto":
        tagged = _analyze_track_from_tags(path, target_db=target_db, allow_empty=True)
        if tagged is not None:
            return tagged

    try:
        raw_db, max_amp, min_g, max_g = _get_processor().analyze_track_metrics(
            path,
            include_gain=not max_amp_only,
        )
        track_gain_db = raw_db
        volume_db = target_db - raw_db
        clip_track = max_amp * _db_to_linear(track_gain_db) if max_amp else None
        clipping = clip_track is not None and clip_track > 32767.0
    except Exception as exc:
        return FileResult(path=path, ok=False, error_msg=str(exc))

    return FileResult(
        path=path,
        ok=True,
        volume_db=volume_db,
        track_gain_db=track_gain_db,
        max_amplitude=max_amp,
        min_gain_field=min_g,
        max_gain_field=max_g,
        clipping=clipping,
        clip_track=clip_track,
    )


def album_group_gain_task(
    path_texts: tuple[str, ...],
    *,
    max_amp_only: bool,
) -> tuple[tuple[str, ...], float | None]:
    group_paths = [Path(path_text) for path_text in path_texts]
    try:
        album_raw_db, _album_min_gain, _album_max_gain, _album_max_amp = (
            _get_processor().analyze_album_metrics(
                group_paths,
                include_gain=not max_amp_only,
            )
        )
        return path_texts, float(album_raw_db)
    except Exception:
        return path_texts, None


def gain_file_task(
    kind: str,
    path_text: str,
    *,
    constant_db: float,
    wrap_gain: bool,
    preserve_dates: bool,
    target_db: float = _LEGACY_TARGET_DB,
    force_apply_normalization: bool = False,
    apply_zero_step: bool = False,
    forced_steps: int | None = None,
) -> FileResult:
    path = Path(path_text)
    options = LegacyCompatOptions(
        wrap_gain=wrap_gain,
        preserve_timestamp=preserve_dates,
        use_temp_file=True,
    )
    try:
        processor = _get_processor()
        if kind == "undo":
            result = processor.undo(path, options=options)
            if result.exit_code != 0:
                return FileResult(path=path, ok=False, error_msg=result.message)
            return FileResult(path=path, ok=True)

        if force_apply_normalization and kind == "apply_track":
            analyzed_gain_db, _max_amp, _min_gain, _max_gain = (
                processor.analyze_track_metrics(
                    path,
                    include_gain=True,
                )
            )
            analyzed_steps = db_to_legacy_steps(analyzed_gain_db)
            steps = analyzed_steps + _target_offset_steps(target_db)
        elif force_apply_normalization and kind == "apply_album":
            if forced_steps is None:
                return FileResult(
                    path=path,
                    ok=False,
                    error_msg="Album analysis failed before apply normalization.",
                )
            steps = forced_steps
        elif kind == "apply_constant":
            gain_db = constant_db
            steps = db_to_legacy_steps(gain_db)
        elif kind == "apply_track":
            tags = read_tags(path)
            gain_db = tags.track_gain_db if tags.track_gain_db is not None else 0.0
            steps = db_to_legacy_steps(gain_db)
        elif kind == "apply_album":
            tags = read_tags(path)
            if tags.album_gain_db is not None:
                gain_db = tags.album_gain_db
            elif tags.track_gain_db is not None:
                gain_db = tags.track_gain_db
            else:
                gain_db = 0.0
            steps = db_to_legacy_steps(gain_db)
        else:
            return FileResult(
                path=path, ok=False, error_msg=f"Unsupported gain task kind: {kind}"
            )

        if (
            force_apply_normalization
            and kind in {"apply_track", "apply_album"}
            and steps == 0
            and not apply_zero_step
        ):
            return FileResult(path=path, ok=True)

        result = processor.apply_steps(
            path,
            left_steps=steps,
            options=options,
        )
        if result.exit_code != 0:
            return FileResult(path=path, ok=False, error_msg=result.message)
    except Exception as exc:
        return FileResult(path=path, ok=False, error_msg=str(exc))
    return FileResult(path=path, ok=True)


def delete_tags_file_task(
    path_text: str, *, tag_mode: str | None = "apev2"
) -> FileResult:
    path = Path(path_text)
    try:
        tag_format: Literal["apev2", "id3"] | None
        if tag_mode in {"apev2", "id3"}:
            tag_format = cast("Literal['apev2', 'id3']", tag_mode)
        else:
            tag_format = None
        result = _get_processor().delete_mp3gain_tags(path, tag_format=tag_format)
        if result.exit_code != 0:
            return FileResult(path=path, ok=False, error_msg=result.message)
    except Exception as exc:
        return FileResult(path=path, ok=False, error_msg=str(exc))
    return FileResult(path=path, ok=True)
