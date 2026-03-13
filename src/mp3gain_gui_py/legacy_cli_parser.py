"""Argument parsing helpers for the legacy-compatible CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .legacy_cli_models import (
    LegacyCliArgs,
    LegacyCliParseState,
    SingleChannelRequest,
)

if TYPE_CHECKING:
    from ._legacy_exact import StoredTagPolicy


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


def _consume_value(
    argv: list[str], index: int, attached: str, *, switch: str
) -> tuple[str, int]:
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


def _parse_single_channel_value(value: str) -> SingleChannelRequest:
    for sep in (",", ":", ";"):
        if sep in value:
            left, right = value.split(sep, 1)
            return SingleChannelRequest(
                channel_index=_parse_int(left.strip(), switch="/l"),
                steps=_parse_int(right.strip(), switch="/l"),
            )
    raise ValueError(
        f"Invalid attached /l value: {value!r}; expected '<channel>,<steps>'"
    )


def _build_legacy_cli_args(
    *,
    paths: list[Path],
    state: LegacyCliParseState,
) -> LegacyCliArgs:
    return LegacyCliArgs(
        files=tuple(paths),
        quiet=state.quiet,
        table_output=state.table_output,
        stored_tag_policy=state.stored_tag_policy,
        delete_tags_requested=state.delete_tags_requested,
        apply_mode=state.apply_mode,
        undo_requested=state.undo_requested,
        wrap_gain=state.wrap_gain,
        auto_clip=state.auto_clip,
        preserve_timestamp=state.preserve_timestamp,
        use_temp_file=state.use_temp_file,
        clip_confirmed=state.clip_confirmed,
        force_apply=state.force_apply,
        max_amp_only=state.max_amp_only,
        track_only_analysis=state.track_only_analysis,
        db_mod=state.db_mod,
        mp3_gain_mod=state.mp3_gain_mod,
        direct_gain_steps=state.direct_gain_steps,
        single_channel=state.single_channel,
        tag_format=state.tag_format,
        info_mode=state.info_mode,
        info_topic=state.info_topic,
        unrecognized_options=tuple(state.unrecognized_options),
    )


def _apply_info_switch(
    *,
    tokens: list[str],
    index: int,
    switch: str,
    attached: str,
    state: LegacyCliParseState,
) -> int:
    if switch == "?":
        state.info_mode = "help_qmark"
        if attached:
            state.info_topic = attached.strip()
            return index
        if index + 1 < len(tokens) and not _looks_like_switch(tokens[index + 1]):
            state.info_topic = tokens[index + 1].strip()
            return index + 1
        return index
    if switch == "h":
        state.info_mode = "help"
        if attached:
            state.info_topic = attached.strip()
        return index

    state.info_mode = "version"
    return index


def _apply_flag_switch(
    *,
    switch: str,
    token: str,
    state: LegacyCliParseState,
) -> bool:
    if switch == "q":
        state.quiet = True
    elif switch == "o":
        state.table_output = True
    elif switch == "r":
        state.apply_mode = "track"
    elif switch == "a":
        state.apply_mode = "album"
    elif switch == "u":
        state.undo_requested = True
    elif switch == "w":
        state.wrap_gain = True
    elif switch == "k":
        state.auto_clip = True
    elif switch == "p":
        state.preserve_timestamp = True
    elif switch == "t":
        state.use_temp_file = True
    elif switch == "c":
        state.clip_confirmed = True
    elif switch == "f":
        state.force_apply = True
    elif switch == "x":
        state.max_amp_only = True
    else:
        return False
    _ = token
    return True


def _apply_value_switch(
    *,
    tokens: list[str],
    index: int,
    switch: str,
    attached: str,
    state: LegacyCliParseState,
) -> int:
    raw_value, next_index = _consume_value(tokens, index, attached, switch=f"/{switch}")
    if switch == "d":
        state.db_mod = _parse_float(raw_value, switch="/d")
    elif switch == "m":
        state.mp3_gain_mod = _parse_int(raw_value, switch="/m")
    elif switch == "g":
        state.direct_gain_steps = _parse_int(raw_value, switch="/g")
    elif switch == "s":
        (
            state.stored_tag_policy,
            state.delete_tags_requested,
            state.tag_format,
        ) = _parse_scan_code(
            raw_value,
            current_policy=state.stored_tag_policy,
            delete_tags_requested=state.delete_tags_requested,
            tag_format=state.tag_format,
        )
    else:
        raise ValueError(f"Unsupported switch /{switch}")
    return next_index


def _parse_single_channel_switch(
    *,
    tokens: list[str],
    index: int,
    attached: str,
    state: LegacyCliParseState,
) -> int:
    if attached and any(sep in attached for sep in (",", ":", ";")):
        state.single_channel = _parse_single_channel_value(attached)
        return index
    channel_text, next_index = _consume_value(tokens, index, attached, switch="/l")
    steps_text, last_index = _consume_value(tokens, next_index, "", switch="/l")
    state.single_channel = SingleChannelRequest(
        channel_index=_parse_int(channel_text, switch="/l"),
        steps=_parse_int(steps_text, switch="/l"),
    )
    return last_index


def parse_legacy_args(argv: list[str] | None = None) -> LegacyCliArgs:
    tokens = list(argv) if argv is not None else []
    paths: list[Path] = []
    state = LegacyCliParseState()

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not _looks_like_switch(token):
            paths.append(Path(token))
            index += 1
            continue

        switch = token[1:2].lower()
        attached = token[2:]
        if switch in {"v", "h", "?"}:
            index = _apply_info_switch(
                tokens=tokens,
                index=index,
                switch=switch,
                attached=attached,
                state=state,
            )
        elif switch in {"q", "o", "r", "a", "u", "w", "k", "p", "t", "c", "x", "f"}:
            if not _apply_flag_switch(
                switch=switch,
                token=token,
                state=state,
            ):
                state.unrecognized_options.append(token[:2])
        elif switch in {"d", "m", "g", "s"}:
            index = _apply_value_switch(
                tokens=tokens,
                index=index,
                switch=switch,
                attached=attached,
                state=state,
            )
        elif switch == "l":
            index = _parse_single_channel_switch(
                tokens=tokens,
                index=index,
                attached=attached,
                state=state,
            )
        else:
            state.unrecognized_options.append(token[:2])
        index += 1

    return _build_legacy_cli_args(paths=paths, state=state)
