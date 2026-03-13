"""Processing helpers for the legacy-compatible CLI."""

from __future__ import annotations

import copy
import sys
from typing import TYPE_CHECKING

from ._legacy_exact import (
    LegacyCompatOptions,
    LegacyExactProcessor,
    db_to_legacy_steps,
)
from ._legacy_exact.math import legacy_steps_to_db_exact
from ._tags.reader import TagData
from .legacy_cli_models import (
    AlbumSummary,
    LegacyCliArgs,
    PathTagState,
    SingleChannelRequest,
    TrackMetrics,
)
from .legacy_cli_support import (
    apply_gain_and_update_tags,
    clear_recalc_fields,
    format_check_only_table_line,
    format_table_line,
    load_runtime_tags,
    max_no_clip_steps,
    print_info,
    update_album_tags_from_analysis,
    update_track_tags_from_analysis,
    would_clip,
    write_runtime_tags,
)

if TYPE_CHECKING:
    from pathlib import Path


def print_table_header(args: LegacyCliArgs) -> None:
    if not args.table_output:
        return
    if args.stored_tag_policy == "check_only":
        print(
            "File\tMP3 gain\tdB gain\tMax Amplitude\tMax global_gain\tMin global_gain\t"
            "Album gain\tAlbum dB gain\tAlbum Max Amplitude\tAlbum Max global_gain\t"
            "Album Min global_gain"
        )
        return
    if args.undo_requested:
        print("File\tleft global_gain change\tright global_gain change")
        return
    print("File\tMP3 gain\tdB gain\tMax Amplitude\tMax global_gain\tMin global_gain")


def init_processor() -> LegacyExactProcessor:
    try:
        return LegacyExactProcessor()
    except Exception as exc:  # pragma: no cover - defensive for CLI surface
        raise RuntimeError(f"failed to initialize C backend: {exc}") from exc


def handle_info_request(args: LegacyCliArgs) -> int | None:
    for option in args.unrecognized_options:
        print(f"I don't recognize option {option}", file=sys.stderr)

    if args.info_mode == "none":
        return None

    print_info(args.info_mode, args.info_topic)
    if args.files:
        return None
    if args.info_mode == "help_qmark":
        return 1 if not args.info_topic else 0
    return 0


def _album_summary_enabled(args: LegacyCliArgs, existing_paths: list[Path]) -> bool:
    return bool(existing_paths) and all(
        (
            args.apply_mode != "track",
            not args.track_only_analysis,
            args.stored_tag_policy != "check_only",
            not args.undo_requested,
            args.single_channel is None,
            args.direct_gain_steps is None,
            not args.delete_tags_requested,
        )
    )


def _resolve_single_track_album_summary(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    existing_paths: list[Path],
) -> TagData | None:
    if len(existing_paths) != 1 or args.stored_tag_policy != "auto":
        return None
    candidate = load_runtime_tags(
        processor, existing_paths[0], tag_format=args.tag_format
    )
    if (
        candidate.track_gain_db is None
        or candidate.track_peak is None
        or candidate.min_gain is None
        or candidate.max_gain is None
    ):
        return None
    return candidate


def _resolve_album_metrics_from_processor(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    existing_paths: list[Path],
) -> tuple[float, int, int, float]:
    if hasattr(processor, "analyze_album_metrics"):
        return processor.analyze_album_metrics(
            existing_paths,
            include_gain=not args.max_amp_only,
        )
    album_tag_gain = (
        0.0 if args.max_amp_only else processor.analyze_album_gain_db(existing_paths)
    )
    album_min_gain, album_max_gain = processor.analyze_album_minmax_gain(existing_paths)
    album_max_amp = max(
        (processor.analyze_max_amplitude(path) for path in existing_paths),
        default=0.0,
    )
    return album_tag_gain, album_min_gain, album_max_gain, album_max_amp


def prepare_album_summary(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    existing_paths: list[Path],
) -> AlbumSummary:
    summary = AlbumSummary(enabled=_album_summary_enabled(args, existing_paths))
    if not summary.enabled:
        return summary

    single_existing = _resolve_single_track_album_summary(
        args,
        processor=processor,
        existing_paths=existing_paths,
    )
    if single_existing is not None:
        peak_value = single_existing.track_peak
        if peak_value is None:
            peak_value = single_existing.album_peak
        summary.tag_gain = (
            single_existing.album_gain_db
            if single_existing.album_gain_db is not None
            else single_existing.track_gain_db or 0.0
        )
        summary.max_amp = 0.0 if peak_value is None else peak_value * 32768.0
        summary.min_gain = (
            single_existing.min_gain
            if single_existing.min_gain is not None
            else single_existing.album_min_gain
        )
        summary.max_gain = (
            single_existing.max_gain
            if single_existing.max_gain is not None
            else single_existing.album_max_gain
        )
    else:
        (
            summary.tag_gain,
            summary.min_gain,
            summary.max_gain,
            summary.max_amp,
        ) = _resolve_album_metrics_from_processor(
            args,
            processor=processor,
            existing_paths=existing_paths,
        )

    summary.db_gain = summary.tag_gain + args.db_mod
    summary.steps = db_to_legacy_steps(summary.db_gain, mp3_gain_mod=args.mp3_gain_mod)
    if args.apply_mode == "album" and args.auto_clip:
        max_no_clip = max_no_clip_steps(summary.max_amp)
        if max_no_clip is not None and summary.steps > max_no_clip:
            summary.steps = max_no_clip
    return summary


def _build_path_tag_state(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
    skip_tag_updates: bool,
) -> PathTagState:
    loaded_tags = load_runtime_tags(processor, path, tag_format=args.tag_format)
    tags = loaded_tags if not skip_tag_updates else TagData()
    tag_state = PathTagState(
        tags=tags,
        original_tags=copy.deepcopy(loaded_tags),
    )
    if args.stored_tag_policy == "recalc" and not skip_tag_updates:
        tag_state.tag_dirty = clear_recalc_fields(tags)
    return tag_state


def _write_tags_if_needed(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
    tag_state: PathTagState,
    skip_tag_updates: bool,
) -> None:
    if skip_tag_updates or not tag_state.tag_dirty:
        return
    write_runtime_tags(
        processor,
        path,
        tag_state.tags,
        tag_format=args.tag_format,
        preserve_timestamp=args.preserve_timestamp,
    )


def _single_channel_gain_changes(request: SingleChannelRequest) -> tuple[int, int]:
    left = request.steps if request.channel_index == 0 else 0
    right = request.steps if request.channel_index == 1 else 0
    return left, right


def handle_check_only_path(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
) -> bool:
    if args.stored_tag_policy != "check_only":
        return False
    tags = load_runtime_tags(processor, path, tag_format=args.tag_format)
    if args.table_output:
        print(format_check_only_table_line(path, tags))
    elif not args.quiet and tags.track_gain_db is not None:
        steps = db_to_legacy_steps(tags.track_gain_db, mp3_gain_mod=0)
        print(
            f'Recommended "Track" dB change: {tags.track_gain_db:.6f}\n'
            f'Recommended "Track" mp3 gain change: {steps}\n'
            f"Applied step dB (exact): {legacy_steps_to_db_exact(steps):.6f}"
        )
    return True


def _handle_undo_request(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
    options: LegacyCompatOptions,
    tag_state: PathTagState,
) -> int | None:
    if not args.undo_requested:
        return None
    undo_left = tag_state.tags.undo_left
    undo_right = tag_state.tags.undo_right
    if undo_left is not None and undo_right is not None and (undo_left or undo_right):
        result = processor.apply_steps(
            path,
            left_steps=undo_left,
            right_steps=undo_right,
            options=options,
        )
        if result.exit_code != 0:
            if not args.quiet:
                print(f"{path}\tERROR\t{result.message}")
            return 1
        apply_gain_and_update_tags(
            tag_state.tags,
            left_gain_change=undo_left,
            right_gain_change=undo_right,
            wrap_gain=args.wrap_gain,
        )
        write_runtime_tags(
            processor,
            path,
            tag_state.tags,
            tag_format=args.tag_format,
            preserve_timestamp=args.preserve_timestamp,
        )
        return 0

    if args.table_output:
        print(f"{path}\t0\t0")
    elif not args.quiet:
        if tag_state.tags.has_undo:
            print(f"No changes to undo in {path}", file=sys.stderr)
        else:
            print(f"No undo information in {path}", file=sys.stderr)
    return 0


def _handle_single_channel_request(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
    options: LegacyCompatOptions,
    tag_state: PathTagState,
    skip_tag_updates: bool,
) -> int | None:
    if args.single_channel is None:
        return None
    result = processor.apply_single_channel_steps(
        path,
        channel_index=args.single_channel.channel_index,
        steps=args.single_channel.steps,
        options=options,
    )
    left, right = _single_channel_gain_changes(args.single_channel)
    if result.exit_code != 0:
        if not skip_tag_updates:
            apply_gain_and_update_tags(
                tag_state.tags,
                left_gain_change=left,
                right_gain_change=right,
                wrap_gain=args.wrap_gain,
            )
            write_runtime_tags(
                processor,
                path,
                tag_state.tags,
                tag_format=args.tag_format,
                preserve_timestamp=args.preserve_timestamp,
            )
        if not args.quiet:
            print(f"{path}: {result.message}")
        return 1

    if not skip_tag_updates and args.single_channel.steps != 0:
        apply_gain_and_update_tags(
            tag_state.tags,
            left_gain_change=left,
            right_gain_change=right,
            wrap_gain=args.wrap_gain,
        )
        write_runtime_tags(
            processor,
            path,
            tag_state.tags,
            tag_format=args.tag_format,
            preserve_timestamp=args.preserve_timestamp,
        )
    return 0


def _handle_direct_gain_request(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
    options: LegacyCompatOptions,
    tag_state: PathTagState,
    skip_tag_updates: bool,
) -> int | None:
    if args.direct_gain_steps is None:
        return None
    result = processor.apply_direct_gain_steps(
        path,
        steps=args.direct_gain_steps,
        options=options,
    )
    if result.exit_code != 0:
        if not args.quiet:
            print(f"{path}\tERROR\t{result.message}")
        return 1
    if not skip_tag_updates and args.direct_gain_steps != 0:
        apply_gain_and_update_tags(
            tag_state.tags,
            left_gain_change=args.direct_gain_steps,
            right_gain_change=args.direct_gain_steps,
            wrap_gain=args.wrap_gain,
        )
        write_runtime_tags(
            processor,
            path,
            tag_state.tags,
            tag_format=args.tag_format,
            preserve_timestamp=args.preserve_timestamp,
        )
    return 0


def _handle_delete_tags_request(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
) -> int | None:
    if not args.delete_tags_requested:
        return None
    result = processor.delete_mp3gain_tags(path, tag_format=args.tag_format)
    if result.exit_code != 0:
        if not args.quiet:
            print(f"{path}\tERROR\t{result.message}")
        return 1
    return 0


def _resolve_track_metrics(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
    tag_state: PathTagState,
    skip_tag_updates: bool,
) -> TrackMetrics:
    tags = tag_state.tags
    original_tags = tag_state.original_tags
    used_auto_tags = (
        args.stored_tag_policy == "auto"
        and tags.tag_format != "none"
        and tags.track_gain_db is not None
        and tags.track_peak is not None
        and tags.min_gain is not None
        and tags.max_gain is not None
    )
    used_skip_fallback = (
        args.stored_tag_policy == "skip"
        and original_tags.track_gain_db is not None
        and original_tags.track_peak is not None
        and original_tags.min_gain is not None
        and original_tags.max_gain is not None
    )
    if used_auto_tags or used_skip_fallback:
        source_tags = tags if used_auto_tags else original_tags
        return TrackMetrics(
            raw_gain=source_tags.track_gain_db or 0.0,
            max_amp=(source_tags.track_peak or 0.0) * 32768.0,
            min_gain=source_tags.min_gain or 0,
            max_gain=source_tags.max_gain or 0,
        )

    if hasattr(processor, "analyze_track_metrics"):
        raw_gain, max_amp, min_gain, max_gain = processor.analyze_track_metrics(
            path,
            include_gain=not args.max_amp_only,
        )
    else:
        raw_gain = 0.0 if args.max_amp_only else processor.analyze_track_gain_db(path)
        max_amp = processor.analyze_max_amplitude(path)
        min_gain, max_gain = processor.analyze_minmax_gain(path)

    if args.stored_tag_policy in {"recalc", "skip"}:
        if (
            original_tags.track_peak is not None
            and abs(max_amp - (original_tags.track_peak * 32768.0)) >= 1.0
        ):
            max_amp = original_tags.track_peak * 32768.0
        if (
            original_tags.track_gain_db is not None
            and abs(raw_gain - original_tags.track_gain_db) <= 0.1
        ):
            raw_gain = original_tags.track_gain_db

    if not skip_tag_updates:
        tag_state.tag_dirty = (
            update_track_tags_from_analysis(
                tags,
                raw_gain_db=raw_gain,
                max_amp=max_amp,
                min_gain=min_gain,
                max_gain=max_gain,
                max_amp_only=args.max_amp_only,
            )
            or tag_state.tag_dirty
        )
    return TrackMetrics(
        raw_gain=raw_gain,
        max_amp=max_amp,
        min_gain=min_gain,
        max_gain=max_gain,
    )


def _resolve_applied_steps(
    args: LegacyCliArgs,
    *,
    steps: int,
    max_amp: float,
    album_summary: AlbumSummary,
) -> int | None:
    applied_steps = album_summary.steps if args.apply_mode == "album" else steps
    if applied_steps is None:
        return None
    if args.apply_mode == "track" and args.auto_clip:
        max_no_clip = max_no_clip_steps(max_amp)
        if max_no_clip is not None and applied_steps > max_no_clip:
            return max_no_clip
    return applied_steps


def _would_reject_for_clipping(
    args: LegacyCliArgs,
    *,
    max_amp: float,
    applied_steps: int,
) -> bool:
    return (
        args.apply_mode in {"track", "album"}
        and not args.auto_clip
        and not args.clip_confirmed
        and would_clip(max_amp, applied_steps)
    )


def _report_clipping_failure(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
    tag_state: PathTagState,
    skip_tag_updates: bool,
) -> int:
    if not args.quiet:
        print(f"{path}\tERROR\tclipping risk; rerun with /c or /k")
    _write_tags_if_needed(
        args,
        processor=processor,
        path=path,
        tag_state=tag_state,
        skip_tag_updates=skip_tag_updates,
    )
    return 1


def _emit_track_result(
    args: LegacyCliArgs,
    *,
    path: Path,
    steps: int,
    db_gain: float,
    max_amp: float,
    min_gain: int,
    max_gain: int,
) -> None:
    if args.table_output:
        print(
            format_table_line(
                path,
                steps=steps,
                db_gain=db_gain,
                max_amp=max_amp,
                min_gain=min_gain,
                max_gain=max_gain,
            )
        )
        return
    if not args.quiet and args.apply_mode == "none":
        print(
            f'Recommended "Track" dB change: {db_gain:.6f}\n'
            f'Recommended "Track" mp3 gain change: {steps}\n'
            f"Applied step dB (exact): {legacy_steps_to_db_exact(steps):.6f}"
        )


def emit_album_summary(args: LegacyCliArgs, summary: AlbumSummary) -> None:
    if (
        not args.table_output
        or not summary.enabled
        or summary.steps is None
        or summary.db_gain is None
        or summary.max_amp is None
        or args.apply_mode == "track"
        or args.stored_tag_policy == "check_only"
        or args.undo_requested
        or args.single_channel is not None
        or args.direct_gain_steps is not None
        or args.delete_tags_requested
    ):
        return

    if summary.single_track_override is not None:
        (
            summary.steps,
            summary.db_gain,
            summary.max_amp,
            summary.min_gain,
            summary.max_gain,
        ) = summary.single_track_override
    print(
        format_table_line(
            '"Album"',
            steps=summary.steps,
            db_gain=summary.db_gain,
            max_amp=summary.max_amp,
            min_gain=summary.min_gain or 0,
            max_gain=summary.max_gain or 0,
        )
    )


def default_options(args: LegacyCliArgs) -> LegacyCompatOptions:
    return LegacyCompatOptions(
        wrap_gain=args.wrap_gain,
        auto_clip=args.auto_clip,
        preserve_timestamp=args.preserve_timestamp,
        use_temp_file=args.use_temp_file,
        tag_format=args.tag_format,
        stored_tag_policy=args.stored_tag_policy,
    )


def process_standard_path(
    args: LegacyCliArgs,
    *,
    processor: LegacyExactProcessor,
    path: Path,
    options: LegacyCompatOptions,
    skip_tag_updates: bool,
    existing_paths: list[Path],
    album_summary: AlbumSummary,
) -> int:
    tag_state = _build_path_tag_state(
        args,
        processor=processor,
        path=path,
        skip_tag_updates=skip_tag_updates,
    )

    for handler in (
        lambda: _handle_undo_request(
            args,
            processor=processor,
            path=path,
            options=options,
            tag_state=tag_state,
        ),
        lambda: _handle_single_channel_request(
            args,
            processor=processor,
            path=path,
            options=options,
            tag_state=tag_state,
            skip_tag_updates=skip_tag_updates,
        ),
        lambda: _handle_direct_gain_request(
            args,
            processor=processor,
            path=path,
            options=options,
            tag_state=tag_state,
            skip_tag_updates=skip_tag_updates,
        ),
        lambda: _handle_delete_tags_request(
            args,
            processor=processor,
            path=path,
        ),
    ):
        outcome = handler()
        if outcome is not None:
            return outcome

    metrics = _resolve_track_metrics(
        args,
        processor=processor,
        path=path,
        tag_state=tag_state,
        skip_tag_updates=skip_tag_updates,
    )
    base_gain = (
        tag_state.tags.track_gain_db
        if (
            args.max_amp_only
            and args.stored_tag_policy == "auto"
            and tag_state.tags.track_gain_db is not None
        )
        else metrics.raw_gain
    )
    db_gain = base_gain + args.db_mod
    steps = db_to_legacy_steps(db_gain, mp3_gain_mod=args.mp3_gain_mod)

    if (
        album_summary.enabled
        and album_summary.max_amp is not None
        and album_summary.min_gain is not None
        and album_summary.max_gain is not None
        and (len(existing_paths) > 1 or args.apply_mode == "album")
        and not skip_tag_updates
    ):
        tag_state.tag_dirty = (
            update_album_tags_from_analysis(
                tag_state.tags,
                album_gain_db=album_summary.tag_gain,
                album_max_amp=album_summary.max_amp,
                album_min_gain=album_summary.min_gain,
                album_max_gain=album_summary.max_gain,
                max_amp_only=args.max_amp_only,
            )
            or tag_state.tag_dirty
        )

    if len(existing_paths) == 1 and args.stored_tag_policy in {"skip", "recalc"}:
        album_summary.single_track_override = (
            steps,
            db_gain,
            metrics.max_amp,
            metrics.min_gain,
            metrics.max_gain,
        )

    applied_steps = _resolve_applied_steps(
        args,
        steps=steps,
        max_amp=metrics.max_amp,
        album_summary=album_summary,
    )
    if applied_steps is None:
        _write_tags_if_needed(
            args,
            processor=processor,
            path=path,
            tag_state=tag_state,
            skip_tag_updates=skip_tag_updates,
        )
        _emit_track_result(
            args,
            path=path,
            steps=steps,
            db_gain=db_gain,
            max_amp=metrics.max_amp,
            min_gain=metrics.min_gain,
            max_gain=metrics.max_gain,
        )
        return 0

    if _would_reject_for_clipping(
        args, max_amp=metrics.max_amp, applied_steps=applied_steps
    ):
        return _report_clipping_failure(
            args,
            processor=processor,
            path=path,
            tag_state=tag_state,
            skip_tag_updates=skip_tag_updates,
        )

    if args.apply_mode in {"track", "album"} and applied_steps != 0:
        if not args.table_output:
            print(path)
            print(f"Applying mp3 gain change of {applied_steps} to {path}...")
        result = processor.apply_steps(path, left_steps=applied_steps, options=options)
        if result.exit_code != 0:
            if not args.quiet:
                print(f"{path}\tERROR\t{result.message}")
            return 1
        if not skip_tag_updates:
            apply_gain_and_update_tags(
                tag_state.tags,
                left_gain_change=applied_steps,
                right_gain_change=applied_steps,
                wrap_gain=args.wrap_gain,
            )
            tag_state.tag_dirty = True

    _write_tags_if_needed(
        args,
        processor=processor,
        path=path,
        tag_state=tag_state,
        skip_tag_updates=skip_tag_updates,
    )
    _emit_track_result(
        args,
        path=path,
        steps=steps,
        db_gain=db_gain,
        max_amp=metrics.max_amp,
        min_gain=metrics.min_gain,
        max_gain=metrics.max_gain,
    )
    return 0
