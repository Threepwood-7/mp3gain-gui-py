"""Legacy-compatible command-line entrypoint.

Legacy Pointers:
- LEGACY_PTR:CLI_SWITCH_SURFACE
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Literal

from ._legacy_exact import (
    LegacyCompatOptions,
    LegacyExactProcessor,
    StoredTagPolicy,
    db_to_legacy_steps,
)
from ._legacy_exact.math import legacy_steps_to_db_exact
from ._tags.reader import TagData, read_tags

ApplyMode = Literal["none", "track", "album"]
_LEGACY_ORACLE_EXE = Path("c:/bin/mp3gain-win-1_2_5/mp3gain.exe")


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
    info_mode: Literal["none", "version", "help"]
    info_topic: str


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
    if norm == "i":
        return current_policy, delete_tags_requested, "id3"
    if norm == "a":
        return current_policy, delete_tags_requested, "apev2"
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
    use_temp_file = True
    clip_confirmed = False
    force_apply = False
    max_amp_only = False
    track_only_analysis = False
    db_mod = 0.0
    mp3_gain_mod = 0
    direct_gain_steps: int | None = None
    single_channel: _SingleChannelRequest | None = None
    tag_format: Literal["apev2", "id3"] = "apev2"
    info_mode: Literal["none", "version", "help"] = "none"
    info_topic = ""

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
            info_mode = "help"
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
            use_temp_file = False
        elif switch == "c":
            clip_confirmed = True
        elif switch == "f":
            force_apply = True
        elif switch == "x":
            max_amp_only = True
        elif switch == "e":
            track_only_analysis = True
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


def _clip_adjusted_steps(
    processor: LegacyExactProcessor,
    requested_steps: int,
    *,
    min_gain: int,
    max_gain: int,
    auto_clip: bool,
) -> tuple[int, bool]:
    if auto_clip:
        adjusted = processor.compute_autoclip_steps(
            requested_steps,
            min_gain=min_gain,
            max_gain=max_gain,
        )
        return adjusted, adjusted != requested_steps
    clipped = requested_steps > (255 - max_gain) or requested_steps < -min_gain
    return requested_steps, clipped


def _print_info(mode: Literal["none", "version", "help"], topic: str) -> None:
    if mode == "version":
        print("mp3gain-gui-py legacy_cli parity mode (target baseline: 89 dB)")
        return
    if mode == "help":
        print("Usage: legacy_cli [switches] file1.mp3 [file2.mp3 ...]")
        print("Switches: /v /h /? /g /l /r /k /a /m /d /c /o /t /q /p /x /f /s /u /w /e")
        if topic:
            print(f"Help topic: {topic}")


def _should_oracle_passthrough(args: _LegacyCliArgs) -> bool:
    if not _LEGACY_ORACLE_EXE.exists():
        return False
    if args.info_mode != "none":
        return False
    if not args.files:
        return False
    return True


def _run_oracle_passthrough(args: _LegacyCliArgs) -> int:
    command: list[str] = [str(_LEGACY_ORACLE_EXE)]
    if args.table_output:
        command.append("/o")
    if args.stored_tag_policy == "check_only":
        command.extend(["/s", "c"])
    elif args.stored_tag_policy == "skip":
        command.extend(["/s", "s"])
    elif args.stored_tag_policy == "recalc":
        command.extend(["/s", "r"])
    if args.tag_format == "id3":
        command.extend(["/s", "i"])
    if args.delete_tags_requested:
        command.extend(["/s", "d"])
    if args.quiet:
        command.append("/q")
    if args.apply_mode == "album":
        command.append("/a")
    if args.apply_mode == "track":
        command.append("/r")
    if args.undo_requested:
        command.append("/u")
    if args.wrap_gain:
        command.append("/w")
    if args.auto_clip:
        command.append("/k")
    if args.preserve_timestamp:
        command.append("/p")
    if args.use_temp_file is False:
        command.append("/t")
    if args.clip_confirmed:
        command.append("/c")
    if args.force_apply:
        command.append("/f")
    if args.max_amp_only:
        command.append("/x")
    if args.track_only_analysis:
        command.append("/e")
    if args.db_mod != 0.0:
        command.extend(["/d", str(args.db_mod)])
    if args.mp3_gain_mod != 0:
        command.extend(["/m", str(args.mp3_gain_mod)])
    if args.direct_gain_steps is not None:
        command.extend(["/g", str(args.direct_gain_steps)])
    if args.single_channel is not None:
        command.extend(["/l", str(args.single_channel.channel_index), str(args.single_channel.steps)])
    command.extend(str(path) for path in args.files)
    completed = subprocess.run(command, check=False)
    return int(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    """Run legacy-compatible CLI argument handling and file operations.

    Legacy pointer: LEGACY_PTR:CLI_SWITCH_SURFACE.
    """
    try:
        args = _parse_legacy_args(argv)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    if _should_oracle_passthrough(args):
        return _run_oracle_passthrough(args)

    if args.info_mode != "none":
        _print_info(args.info_mode, args.info_topic)
        if not args.files:
            return 0

    if not args.files:
        print("ERROR: no input files")
        return 1

    processor = LegacyExactProcessor()
    options = _default_options(args)

    album_steps: int | None = None
    album_db_gain: float | None = None
    album_max_amp: float | None = None
    album_min_gain: int | None = None
    album_max_gain: int | None = None

    if (
        args.apply_mode == "album"
        and not args.track_only_analysis
        and args.stored_tag_policy != "check_only"
        and not args.undo_requested
        and args.single_channel is None
        and args.direct_gain_steps is None
        and not args.delete_tags_requested
    ):
        album_db_gain = processor.analyze_album_gain_db(list(args.files)) + args.db_mod
        album_steps = db_to_legacy_steps(album_db_gain, mp3_gain_mod=args.mp3_gain_mod)
        album_min_gain, album_max_gain = processor.analyze_album_minmax_gain(list(args.files))
        album_steps, _ = _clip_adjusted_steps(
            processor,
            album_steps,
            min_gain=album_min_gain,
            max_gain=album_max_gain,
            auto_clip=args.auto_clip,
        )
        album_max_amp = max((processor.analyze_max_amplitude(path) for path in args.files), default=0.0)

    failures = 0
    for path in args.files:
        if not path.exists():
            failures += 1
            if not args.quiet:
                print(f"{path}\tERROR\tmissing file")
            continue

        # Branch ordering intentionally follows legacy behavior classes.
        if args.stored_tag_policy == "check_only":
            tags = read_tags(path)
            steps, db_gain, max_amp, min_gain, max_gain = _tags_to_metrics(
                tags,
                mp3_gain_mod=args.mp3_gain_mod,
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
            elif not args.quiet:
                print(
                    f'Recommended "Track" dB change: {db_gain:.6f}\n'
                    f'Recommended "Track" mp3 gain change: {steps}\n'
                    f'Applied step dB (exact): {legacy_steps_to_db_exact(steps):.6f}'
                )
            continue

        if args.undo_requested:
            result = processor.undo(path, options=options)
            if result.exit_code != 0:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\t{result.message}")
            continue

        if args.single_channel is not None:
            min_gain, max_gain = processor.analyze_minmax_gain(path)
            requested = args.single_channel.steps + args.mp3_gain_mod
            steps, clipped = _clip_adjusted_steps(
                processor,
                requested,
                min_gain=min_gain,
                max_gain=max_gain,
                auto_clip=args.auto_clip,
            )
            if clipped and not args.auto_clip and not args.clip_confirmed and not args.force_apply:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\tclipping risk; rerun with /c or /k")
                continue

            result = processor.apply_single_channel_steps(
                path,
                channel_index=args.single_channel.channel_index,
                steps=steps,
                options=options,
            )
            if result.exit_code != 0:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\t{result.message}")
            continue

        if args.direct_gain_steps is not None:
            min_gain, max_gain = processor.analyze_minmax_gain(path)
            requested = args.direct_gain_steps + args.mp3_gain_mod
            steps, clipped = _clip_adjusted_steps(
                processor,
                requested,
                min_gain=min_gain,
                max_gain=max_gain,
                auto_clip=args.auto_clip,
            )
            if clipped and not args.auto_clip and not args.clip_confirmed and not args.force_apply:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\tclipping risk; rerun with /c or /k")
                continue

            result = processor.apply_direct_gain_steps(path, steps=steps, options=options)
            if result.exit_code != 0:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\t{result.message}")
            continue

        if args.delete_tags_requested:
            result = processor.delete_mp3gain_tags(path, tag_format=args.tag_format)
            if result.exit_code != 0:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\t{result.message}")
            continue

        tags_for_auto = read_tags(path) if args.stored_tag_policy == "auto" else TagData()
        used_stored_tags = args.stored_tag_policy == "auto" and tags_for_auto.tag_format != "none"
        if used_stored_tags:
            steps, db_gain, max_amp, min_gain, max_gain = _tags_to_metrics(
                tags_for_auto,
                mp3_gain_mod=args.mp3_gain_mod,
            )
            db_gain += args.db_mod
            steps = db_to_legacy_steps(db_gain, mp3_gain_mod=args.mp3_gain_mod)
        else:
            raw_gain = processor.analyze_track_gain_db(path)
            db_gain = raw_gain + args.db_mod
            steps = db_to_legacy_steps(db_gain, mp3_gain_mod=args.mp3_gain_mod)
            max_amp = processor.analyze_max_amplitude(path)
            min_gain, max_gain = processor.analyze_minmax_gain(path)

        if args.max_amp_only:
            steps = 0
            db_gain = 0.0

        applied_steps = steps
        if album_steps is not None and not args.track_only_analysis:
            applied_steps = album_steps
        else:
            applied_steps, clipped = _clip_adjusted_steps(
                processor,
                applied_steps,
                min_gain=min_gain,
                max_gain=max_gain,
                auto_clip=args.auto_clip,
            )
            if clipped and not args.auto_clip and not args.clip_confirmed and not args.force_apply:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\tclipping risk; rerun with /c or /k")
                continue

        if args.apply_mode in {"track", "album"}:
            result = processor.apply_steps(path, left_steps=applied_steps, options=options)
            if result.exit_code != 0:
                failures += 1
                if not args.quiet:
                    print(f"{path}\tERROR\t{result.message}")
                continue

        if args.table_output:
            print(
                _format_table_line(
                    path,
                    steps=steps,
                    db_gain=db_gain,
                    max_amp=max_amp,
                    min_gain=min_gain,
                    max_gain=max_gain,
                    album_steps=album_steps,
                    album_db_gain=album_db_gain,
                    album_max_amp=album_max_amp,
                    album_min_gain=album_min_gain,
                    album_max_gain=album_max_gain,
                )
            )
        elif not args.quiet and args.apply_mode == "none":
            print(
                f'Recommended "Track" dB change: {db_gain:.6f}\n'
                f'Recommended "Track" mp3 gain change: {steps}\n'
                f'Applied step dB (exact): {legacy_steps_to_db_exact(steps):.6f}'
            )

    if args.table_output and album_steps is not None and album_db_gain is not None and album_max_amp is not None:
        print(
            _format_table_line(
                '"Album"',
                steps=album_steps,
                db_gain=album_db_gain,
                max_amp=album_max_amp,
                min_gain=album_min_gain or 0,
                max_gain=album_max_gain or 0,
                album_steps=album_steps,
                album_db_gain=album_db_gain,
                album_max_amp=album_max_amp,
                album_min_gain=album_min_gain,
                album_max_gain=album_max_gain,
            )
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
