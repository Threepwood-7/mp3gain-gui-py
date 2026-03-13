"""Shared dataclasses for the legacy-compatible CLI implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

    from ._legacy_exact import StoredTagPolicy
    from ._tags.reader import TagData

ApplyMode = Literal["none", "track", "album"]


@dataclass(frozen=True)
class SingleChannelRequest:
    channel_index: int
    steps: int


@dataclass(frozen=True)
class LegacyCliArgs:
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
    single_channel: SingleChannelRequest | None
    tag_format: Literal["apev2", "id3"]
    info_mode: Literal["none", "version", "help", "help_qmark"]
    info_topic: str
    unrecognized_options: tuple[str, ...]


@dataclass
class LegacyCliParseState:
    quiet: bool = False
    table_output: bool = False
    stored_tag_policy: StoredTagPolicy = "auto"
    delete_tags_requested: bool = False
    apply_mode: ApplyMode = "none"
    undo_requested: bool = False
    wrap_gain: bool = False
    auto_clip: bool = False
    preserve_timestamp: bool = False
    use_temp_file: bool = False
    clip_confirmed: bool = False
    force_apply: bool = False
    max_amp_only: bool = False
    track_only_analysis: bool = False
    db_mod: float = 0.0
    mp3_gain_mod: int = 0
    direct_gain_steps: int | None = None
    single_channel: SingleChannelRequest | None = None
    tag_format: Literal["apev2", "id3"] = "apev2"
    info_mode: Literal["none", "version", "help", "help_qmark"] = "none"
    info_topic: str = ""
    unrecognized_options: list[str] = field(default_factory=list)


@dataclass
class AlbumSummary:
    enabled: bool
    steps: int | None = None
    db_gain: float | None = None
    max_amp: float | None = None
    min_gain: int | None = None
    max_gain: int | None = None
    tag_gain: float = 0.0
    single_track_override: tuple[int, float, float, int, int] | None = None


@dataclass
class PathTagState:
    tags: TagData
    original_tags: TagData
    tag_dirty: bool = False


@dataclass(frozen=True)
class TrackMetrics:
    raw_gain: float
    max_amp: float
    min_gain: int
    max_gain: int
