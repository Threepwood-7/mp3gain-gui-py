"""Legacy-compatible command-line entrypoint.

Legacy Pointers:
- LEGACY_PTR:CLI_SWITCH_SURFACE
"""

from __future__ import annotations

import copy
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ._legacy_exact import (
    LegacyCompatOptions,
    LegacyExactProcessor,
    StoredTagPolicy,
    db_to_legacy_steps,
)
from ._legacy_exact.math import legacy_steps_to_db_exact
from ._tags.reader import TagData

ApplyMode = Literal["none", "track", "album"]


@dataclass(frozen=True)
class _SingleChannelRequest:
    channel_index: int
    steps: int


@dataclass(frozen=True)
class _LegacyCliArgs:
    files: tuple[Path, ...]
    quiet: bool
    table_output: bool
    stored_tag_policy: StoredTagPolicy
    delete_tags_requested: bool
    apply_mode: ApplyMode
    undo_requested: bool
    wrap_gain: bool
    auto_clip: bool
    preserve_timestamp: bool
    use_temp_file: bool
    clip_confirmed: bool
    force_apply: bool
    max_amp_only: bool
    track_only_analysis: bool
    db_mod: float
    mp3_gain_mod: int
    direct_gain_steps: int | None
    single_channel: _SingleChannelRequest | None
    tag_format: Literal["apev2", "id3"]
    info_mode: Literal["none", "version", "help", "help_qmark"]
    info_topic: str
    unrecognized_options: tuple[str, ...]


def _looks_like_switch(token: str) -> bool:
    return len(token) > 1 and token[0] in "-/" and token != "--"


def _parse_float(value: str, *, switch: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid value for {switch}: {value!r}") from exc


def _parse_int(value: str, *, switch: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid value for {switch}: {value!r}") from exc


def _consume_value(argv: list[str], index: int, attached: str, *, switch: str) -> tuple[str, int]:
    if attached:
        return attached, index
    next_index = index + 1
    if next_index >= len(argv):
        raise ValueError(f"Missing value for {switch}")
    return argv[next_index], next_index


def _parse_scan_code(
    code: str,
    *,
    current_policy: StoredTagPolicy,
    delete_tags_requested: bool,
    tag_format: Literal["apev2", "id3"],
) -> tuple[StoredTagPolicy, bool, Literal["apev2", "id3"]]:
    norm = code.strip().lower()
    if norm == "c":
        return "check_only", False, tag_format
    if norm == "s":
        return "skip", False, tag_format
    if norm == "r":
        return "recalc", False, tag_format
    if norm == "d":
        return current_policy, True, tag_format
    # mp3gain.exe 1.4.6 (used as oracle) does not accept /s i or /s a.
    if norm in {"i", "a"}:
        raise ValueError(f"Unsupported /s mode for this legacy binary: {code!r}")
    raise ValueError(f"Unsupported /s mode: {code!r}")


def _parse_single_channel_value(value: str) -> _SingleChannelRequest:
    for sep in (",", ":", ";"):
        if sep in value:
            left, right = value.split(sep, 1)
            return _SingleChannelRequest(
                channel_index=_parse_int(left.strip(), switch="/l"),
                steps=_parse_int(right.strip(), switch="/l"),
            )
    raise ValueError(f"Invalid attached /l value: {value!r}; expected '<channel>,<steps>'")


def _parse_legacy_args(argv: list[str] | None) -> _LegacyCliArgs:
    tokens = list(sys.argv[1:] if argv is None else argv)
    paths: list[Path] = []
    quiet = False
    table_output = False
    stored_tag_policy: StoredTagPolicy = "auto"
    delete_tags_requested = False
    apply_mode: ApplyMode = "none"
    undo_requested = False
    wrap_gain = False
    auto_clip = False
    preserve_timestamp = False
    use_temp_file = False
    clip_confirmed = False
    force_apply = False
    max_amp_only = False
    track_only_analysis = False
    db_mod = 0.0
    mp3_gain_mod = 0
    direct_gain_steps: int | None = None
    single_channel: _SingleChannelRequest | None = None
    tag_format: Literal["apev2", "id3"] = "apev2"
    info_mode: Literal["none", "version", "help", "help_qmark"] = "none"
    info_topic = ""
    unrecognized_options: list[str] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "--":
            paths.extend(Path(item) for item in tokens[i + 1 :])
            break
        if not _looks_like_switch(token):
            paths.append(Path(token))
            i += 1
            continue

        switch = token[1:2].lower()
        attached = token[2:]

        if switch == "?":
            info_mode = "help_qmark"
            if attached:
                info_topic = attached.strip()
            elif i + 1 < len(tokens) and not _looks_like_switch(tokens[i + 1]):
                info_topic = tokens[i + 1].strip()
                i += 1
        elif switch == "h":
            info_mode = "help"
            if attached:
                info_topic = attached.strip()
        elif switch == "v":
            info_mode = "version"
        elif switch == "q":
            quiet = True
        elif switch == "o":
            table_output = True
        elif switch == "r":
            apply_mode = "track"
        elif switch == "a":
            apply_mode = "album"
        elif switch == "u":
            undo_requested = True
        elif switch == "w":
            wrap_gain = True
        elif switch == "k":
            auto_clip = True
        elif switch == "p":
            preserve_timestamp = True
        elif switch == "t":
            use_temp_file = True
        elif switch == "c":
            clip_confirmed = True
        elif switch == "f":
            force_apply = True
        elif switch == "x":
            max_amp_only = True
        elif switch == "e":
            # Legacy mp3gain.exe 1.4.6 treats /e as unrecognized.
            unrecognized_options.append(token)
        elif switch == "d":
            value, i = _consume_value(tokens, i, attached, switch="/d")
            db_mod = _parse_float(value, switch="/d")
        elif switch == "m":
            value, i = _consume_value(tokens, i, attached, switch="/m")
            mp3_gain_mod = _parse_int(value, switch="/m")
        elif switch == "g":
            value, i = _consume_value(tokens, i, attached, switch="/g")
            direct_gain_steps = _parse_int(value, switch="/g")
        elif switch == "l":
            if attached:
                single_channel = _parse_single_channel_value(attached)
            else:
                if i + 2 >= len(tokens):
                    raise ValueError("Missing '/l <channel> <steps>' arguments")
                channel = _parse_int(tokens[i + 1], switch="/l")
                steps = _parse_int(tokens[i + 2], switch="/l")
                single_channel = _SingleChannelRequest(channel_index=channel, steps=steps)
                i += 2
        elif switch == "s":
            value, i = _consume_value(tokens, i, attached, switch="/s")
            stored_tag_policy, delete_tags_requested, tag_format = _parse_scan_code(
                value,
                current_policy=stored_tag_policy,
                delete_tags_requested=delete_tags_requested,
                tag_format=tag_format,
            )
        else:
            raise ValueError(f"Unsupported switch: {token}")

        i += 1

    return _LegacyCliArgs(
        files=tuple(paths),
        quiet=quiet,
        table_output=table_output,
        stored_tag_policy=stored_tag_policy,
        delete_tags_requested=delete_tags_requested,
        apply_mode=apply_mode,
        undo_requested=undo_requested,
        wrap_gain=wrap_gain,
        auto_clip=auto_clip,
        preserve_timestamp=preserve_timestamp,
        use_temp_file=use_temp_file,
        clip_confirmed=clip_confirmed,
        force_apply=force_apply,
        max_amp_only=max_amp_only,
        track_only_analysis=track_only_analysis,
        db_mod=db_mod,
        mp3_gain_mod=mp3_gain_mod,
        direct_gain_steps=direct_gain_steps,
        single_channel=single_channel,
        tag_format=tag_format,
        info_mode=info_mode,
        info_topic=info_topic,
        unrecognized_options=tuple(unrecognized_options),
    )


def _default_options(args: _LegacyCliArgs) -> LegacyCompatOptions:
    return LegacyCompatOptions(
        wrap_gain=args.wrap_gain,
        auto_clip=args.auto_clip,
        preserve_timestamp=args.preserve_timestamp,
        use_temp_file=args.use_temp_file,
        tag_format=args.tag_format,
        stored_tag_policy=args.stored_tag_policy,
    )


def _tags_to_metrics(tags: TagData, *, mp3_gain_mod: int) -> tuple[int, float, float, int, int]:
    track_gain = tags.track_gain_db if tags.track_gain_db is not None else 0.0
    steps = db_to_legacy_steps(track_gain, mp3_gain_mod=mp3_gain_mod)
    max_amp = (tags.track_peak or 0.0) * 32768.0
    min_gain = tags.min_gain if tags.min_gain is not None else 0
    max_gain = tags.max_gain if tags.max_gain is not None else 0
    return steps, track_gain, max_amp, min_gain, max_gain


def _format_table_line(
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


def _print_info(mode: Literal["none", "version", "help", "help_qmark"], topic: str) -> None:
    if mode == "version":
        print("mp3gain-gui-py legacy_cli parity mode (target baseline: 89 dB)")
        return
    if mode in {"help", "help_qmark"}:
        print("Usage: legacy_cli [switches] file1.mp3 [file2.mp3 ...]")
        print("Switches: /v /h /? /g /l /r /k /a /m /d /c /o /t /q /p /x /f /s /u /w /e")
        if topic:
            print(f"Help topic: {topic}")


def _load_runtime_tags(
    processor: LegacyExactProcessor,
    path: Path,
    *,
    tag_format: Literal["apev2", "id3"],
) -> TagData:
    tags = processor.read_replaygain_tags(path)
    # Legacy binary defaults to APEv2 mode and ignores ID3-only ReplayGain tags.
    if tag_format == "apev2" and tags.tag_format == "id3":
        return TagData(tag_format="none")
    return tags


def _clear_recalc_fields(tags: TagData) -> bool:
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


def _update_track_tags_from_analysis(
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


def _update_album_tags_from_analysis(
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


def _apply_gain_and_update_tags(
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
            tags.album_min_gain = 0 if tags.album_min_gain == 0 else _clamp_gain_byte(cur_min)
            tags.album_max_gain = _clamp_gain_byte(cur_max)


def _write_runtime_tags(
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


def _max_no_clip_steps(max_amp: float) -> int | None:
    if max_amp <= 0.0:
        return None
    return math.floor(4.0 * math.log10(32767.0 / max_amp) / math.log10(2.0))


def _would_clip(max_amp: float, gain_steps: int) -> bool:
    return max_amp * math.pow(2.0, float(gain_steps) / 4.0) > 32767.0


def _format_check_only_value_int(value: int | None) -> str:
    return "NA" if value is None else str(value)


def _format_check_only_value_float(value: float | None) -> str:
    return "NA" if value is None else f"{value:.6f}"


def _format_check_only_table_line(path: Path, tags: TagData) -> str:
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


def main(argv: list[str] | None = None) -> int:
    """Run legacy-compatible CLI argument handling and file operations.

    Legacy pointer: LEGACY_PTR:CLI_SWITCH_SURFACE.
    """
    try:
        args = _parse_legacy_args(argv)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for option in args.unrecognized_options:
        print(f"I don't recognize option {option}", file=sys.stderr)

    if args.info_mode != "none":
        _print_info(args.info_mode, args.info_topic)
        if not args.files:
            if args.info_mode == "help_qmark":
                return 1 if not args.info_topic else 0
            return 0

    if not args.files:
        print("ERROR: no input files", file=sys.stderr)
        return 1

    if args.table_output:
        if args.stored_tag_policy == "check_only":
            print(
                "File\tMP3 gain\tdB gain\tMax Amplitude\tMax global_gain\tMin global_gain\t"
                "Album gain\tAlbum dB gain\tAlbum Max Amplitude\tAlbum Max global_gain\t"
                "Album Min global_gain"
            )
        elif args.undo_requested:
            print("File\tleft global_gain change\tright global_gain change")
        else:
            print("File\tMP3 gain\tdB gain\tMax Amplitude\tMax global_gain\tMin global_gain")

    try:
        processor = LegacyExactProcessor()
    except Exception as exc:  # pragma: no cover - defensive for CLI surface
        print(f"ERROR: failed to initialize C backend: {exc}", file=sys.stderr)
        return 1
    options = _default_options(args)

    existing_paths = [path for path in args.files if path.exists()]
    skip_tag_updates = args.stored_tag_policy == "skip" and not args.undo_requested

    album_summary_enabled = (
        bool(existing_paths)
        and args.apply_mode != "track"
        and not args.track_only_analysis
        and args.stored_tag_policy != "check_only"
        and not args.undo_requested
        and args.single_channel is None
        and args.direct_gain_steps is None
        and not args.delete_tags_requested
    )
    album_steps: int | None = None
    album_db_gain: float | None = None
    album_max_amp: float | None = None
    album_min_gain: int | None = None
    album_max_gain: int | None = None
    album_tag_gain: float = 0.0
    single_track_album_override: tuple[int, float, float, int, int] | None = None

    if album_summary_enabled:
        single_existing = None
        if (
            len(existing_paths) == 1
            and args.stored_tag_policy == "auto"
            and args.stored_tag_policy != "recalc"
        ):
            candidate = _load_runtime_tags(processor, existing_paths[0], tag_format=args.tag_format)
            if (
                candidate.track_gain_db is not None
                and candidate.track_peak is not None
                and candidate.min_gain is not None
                and candidate.max_gain is not None
            ):
                single_existing = candidate

        if single_existing is not None:
            if single_existing.album_gain_db is not None:
                album_tag_gain = single_existing.album_gain_db
            else:
                album_tag_gain = single_existing.track_gain_db or 0.0
            album_db_gain = album_tag_gain + args.db_mod
            album_steps = db_to_legacy_steps(album_db_gain, mp3_gain_mod=args.mp3_gain_mod)
            album_max_amp = (
                (single_existing.track_peak if single_existing.track_peak is not None else single_existing.album_peak)
                * 32768.0
            )
            album_min_gain = (
                single_existing.min_gain
                if single_existing.min_gain is not None
                else single_existing.album_min_gain
            )
            album_max_gain = (
                single_existing.max_gain
                if single_existing.max_gain is not None
                else single_existing.album_max_gain
            )
        else:
            if hasattr(processor, "analyze_album_metrics"):
                album_tag_gain, album_min_gain, album_max_gain, album_max_amp = processor.analyze_album_metrics(
                    existing_paths,
                    include_gain=not args.max_amp_only,
                )
            else:
                album_tag_gain = 0.0 if args.max_amp_only else processor.analyze_album_gain_db(existing_paths)
                album_min_gain, album_max_gain = processor.analyze_album_minmax_gain(existing_paths)
                album_max_amp = max((processor.analyze_max_amplitude(path) for path in existing_paths), default=0.0)
            album_db_gain = album_tag_gain + args.db_mod
            album_steps = db_to_legacy_steps(album_db_gain, mp3_gain_mod=args.mp3_gain_mod)
        if args.apply_mode == "album" and args.auto_clip and album_steps is not None and album_max_amp is not None:
            max_no_clip = _max_no_clip_steps(album_max_amp)
            if max_no_clip is not None and album_steps > max_no_clip:
                album_steps = max_no_clip

    failures = 0
    for path in args.files:
        if not path.exists():
            failures += 1
            if not args.quiet:
                print(f"{path}\tERROR\tmissing file")
            continue

        # Branch ordering intentionally follows legacy behavior classes.
        if args.stored_tag_policy == "check_only":
            tags = _load_runtime_tags(processor, path, tag_format=args.tag_format)
            if args.table_output:
                print(_format_check_only_table_line(path, tags))
            elif not args.quiet and tags.track_gain_db is not None:
                steps = db_to_legacy_steps(tags.track_gain_db, mp3_gain_mod=0)
                db_gain = tags.track_gain_db
                print(
                    f'Recommended "Track" dB change: {db_gain:.6f}\n'
                    f'Recommended "Track" mp3 gain change: {steps}\n'
                    f'Applied step dB (exact): {legacy_steps_to_db_exact(steps):.6f}'
                )
            continue

        loaded_tags = _load_runtime_tags(processor, path, tag_format=args.tag_format)
        tags = loaded_tags if not skip_tag_updates else TagData()
        original_tags = copy.deepcopy(loaded_tags)
        tag_dirty = False
        if args.stored_tag_policy == "recalc" and not skip_tag_updates:
            tag_dirty = _clear_recalc_fields(tags)

        if args.undo_requested:
            undo_left = tags.undo_left
            undo_right = tags.undo_right
            if undo_left is not None and undo_right is not None and (undo_left != 0 or undo_right != 0):
                result = processor.apply_steps(
                    path,
                    left_steps=undo_left,
                    right_steps=undo_right,
                    options=options,
                )
                if result.exit_code != 0:
                    failures += 1
                    if not args.quiet:
                        print(f"{path}\tERROR\t{result.message}")
                    continue
                _apply_gain_and_update_tags(
                    tags,
                    left_gain_change=undo_left,
                    right_gain_change=undo_right,
                    wrap_gain=args.wrap_gain,
                )
                _write_runtime_tags(
                    processor,
                    path,
                    tags,
                    tag_format=args.tag_format,
                    preserve_timestamp=args.preserve_timestamp,
                )
            elif args.table_output:
                print(f"{path}\t0\t0")
            elif not args.quiet:
                if tags.has_undo:
                    print(f"No changes to undo in {path}", file=sys.stderr)
                else:
                    print(f"No undo information in {path}", file=sys.stderr)
            continue

        if args.single_channel is not None:
            result = processor.apply_single_channel_steps(
                path,
                channel_index=args.single_channel.channel_index,
                steps=args.single_channel.steps,
                options=options,
            )
            if result.exit_code != 0:
                if not skip_tag_updates:
                    left = args.single_channel.steps if args.single_channel.channel_index == 0 else 0
                    right = args.single_channel.steps if args.single_channel.channel_index == 1 else 0
                    _apply_gain_and_update_tags(
                        tags,
                        left_gain_change=left,
                        right_gain_change=right,
                        wrap_gain=args.wrap_gain,
                    )
                    _write_runtime_tags(
                        processor,
                        path,
                        tags,
                        tag_format=args.tag_format,
                        preserve_timestamp=args.preserve_timestamp,
                    )
                failures += 1
                if not args.quiet:
                    print(f"{path}: {result.message}")
                continue
            if not skip_tag_updates and args.single_channel.steps != 0:
                left = args.single_channel.steps if args.single_channel.channel_index == 0 else 0
                right = args.single_channel.steps if args.single_channel.channel_index == 1 else 0
                _apply_gain_and_update_tags(
                    tags,
                    left_gain_change=left,
                    right_gain_change=right,
                    wrap_gain=args.wrap_gain,
                )
                _write_runtime_tags(
                    processor,
                    path,
                    tags,
                    tag_format=args.tag_format,
                    preserve_timestamp=args.preserve_timestamp,
                )
            continue

        if args.direct_gain_steps is not None:
            result = processor.apply_direct_gain_steps(path, steps=args.direct_gain_steps, options=options)
            if result.exit_code != 0:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\t{result.message}")
                continue
            if not skip_tag_updates and args.direct_gain_steps != 0:
                _apply_gain_and_update_tags(
                    tags,
                    left_gain_change=args.direct_gain_steps,
                    right_gain_change=args.direct_gain_steps,
                    wrap_gain=args.wrap_gain,
                )
                _write_runtime_tags(
                    processor,
                    path,
                    tags,
                    tag_format=args.tag_format,
                    preserve_timestamp=args.preserve_timestamp,
                )
            continue

        if args.delete_tags_requested:
            result = processor.delete_mp3gain_tags(path, tag_format=args.tag_format)
            if result.exit_code != 0:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\t{result.message}")
            continue

        used_auto_tags = (
            args.stored_tag_policy == "auto"
            and tags.tag_format != "none"
            and tags.track_gain_db is not None
            and tags.track_peak is not None
            and tags.min_gain is not None
            and tags.max_gain is not None
            and args.stored_tag_policy != "recalc"
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
            raw_gain = source_tags.track_gain_db or 0.0
            max_amp = (source_tags.track_peak or 0.0) * 32768.0
            min_gain = source_tags.min_gain or 0
            max_gain = source_tags.max_gain or 0
        else:
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
                tag_dirty = _update_track_tags_from_analysis(
                    tags,
                    raw_gain_db=raw_gain,
                    max_amp=max_amp,
                    min_gain=min_gain,
                    max_gain=max_gain,
                    max_amp_only=args.max_amp_only,
                ) or tag_dirty

        if args.max_amp_only:
            base_gain = tags.track_gain_db if (args.stored_tag_policy == "auto" and tags.track_gain_db is not None) else 0.0
        else:
            base_gain = raw_gain
        db_gain = base_gain + args.db_mod
        steps = db_to_legacy_steps(db_gain, mp3_gain_mod=args.mp3_gain_mod)

        if (
            album_summary_enabled
            and album_max_amp is not None
            and album_min_gain is not None
            and album_max_gain is not None
            and (len(existing_paths) > 1 or args.apply_mode == "album")
            and not skip_tag_updates
        ):
            tag_dirty = _update_album_tags_from_analysis(
                tags,
                album_gain_db=album_tag_gain,
                album_max_amp=album_max_amp,
                album_min_gain=album_min_gain,
                album_max_gain=album_max_gain,
                max_amp_only=args.max_amp_only,
            ) or tag_dirty

        if len(existing_paths) == 1 and args.stored_tag_policy in {"skip", "recalc"}:
            single_track_album_override = (steps, db_gain, max_amp, min_gain, max_gain)

        applied_steps = steps
        if args.apply_mode == "album" and album_steps is not None:
            applied_steps = album_steps

        if args.apply_mode == "track" and args.auto_clip:
            max_no_clip = _max_no_clip_steps(max_amp)
            if max_no_clip is not None and applied_steps > max_no_clip:
                applied_steps = max_no_clip
        elif args.apply_mode == "track" and not args.clip_confirmed and _would_clip(max_amp, applied_steps):
            failures += 1
            if not args.quiet:
                print(f"{path}\tERROR\tclipping risk; rerun with /c or /k")
            if not skip_tag_updates and tag_dirty:
                _write_runtime_tags(
                    processor,
                    path,
                    tags,
                    tag_format=args.tag_format,
                    preserve_timestamp=args.preserve_timestamp,
                )
            continue

        if args.apply_mode == "album" and not args.auto_clip and not args.clip_confirmed and _would_clip(max_amp, applied_steps):
            failures += 1
            if not args.quiet:
                print(f"{path}\tERROR\tclipping risk; rerun with /c or /k")
            if not skip_tag_updates and tag_dirty:
                _write_runtime_tags(
                    processor,
                    path,
                    tags,
                    tag_format=args.tag_format,
                    preserve_timestamp=args.preserve_timestamp,
                )
            continue

        if args.apply_mode in {"track", "album"} and applied_steps != 0:
            if not args.table_output:
                print(path)
                print(f"Applying mp3 gain change of {applied_steps} to {path}...")
            result = processor.apply_steps(path, left_steps=applied_steps, options=options)
            if result.exit_code != 0:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\t{result.message}")
                continue
            if not skip_tag_updates:
                _apply_gain_and_update_tags(
                    tags,
                    left_gain_change=applied_steps,
                    right_gain_change=applied_steps,
                    wrap_gain=args.wrap_gain,
                )
                tag_dirty = True

        if not skip_tag_updates and tag_dirty:
            _write_runtime_tags(
                processor,
                path,
                tags,
                tag_format=args.tag_format,
                preserve_timestamp=args.preserve_timestamp,
            )

        if args.table_output:
            print(
                _format_table_line(
                    path,
                    steps=steps,
                    db_gain=db_gain,
                    max_amp=max_amp,
                    min_gain=min_gain,
                    max_gain=max_gain,
                )
            )
        elif not args.quiet and args.apply_mode == "none":
            print(
                f'Recommended "Track" dB change: {db_gain:.6f}\n'
                f'Recommended "Track" mp3 gain change: {steps}\n'
                f'Applied step dB (exact): {legacy_steps_to_db_exact(steps):.6f}'
            )

    if (
        args.table_output
        and album_summary_enabled
        and album_steps is not None
        and album_db_gain is not None
        and album_max_amp is not None
        and args.apply_mode != "track"
        and args.stored_tag_policy != "check_only"
        and not args.undo_requested
        and args.single_channel is None
        and args.direct_gain_steps is None
        and not args.delete_tags_requested
    ):
        if single_track_album_override is not None:
            album_steps = single_track_album_override[0]
            album_db_gain = single_track_album_override[1]
            album_max_amp = single_track_album_override[2]
            album_min_gain = single_track_album_override[3]
            album_max_gain = single_track_album_override[4]
        print(
            _format_table_line(
                '"Album"',
                steps=album_steps,
                db_gain=album_db_gain,
                max_amp=album_max_amp,
                min_gain=album_min_gain or 0,
                max_gain=album_max_gain or 0,
            )
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
