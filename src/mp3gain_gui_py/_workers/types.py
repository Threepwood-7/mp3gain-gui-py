"""Worker request/result dataclasses — no Qt imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

OperationKind = Literal[
    "track_analyze",
    "album_analyze",
    "apply_track",
    "apply_album",
    "apply_constant",
    "undo",
    "delete_tags",
]
StoredTagPolicy = Literal["auto", "skip", "recalc", "check_only"]


@dataclass
class WorkerRequest:
    """Describes a background operation to perform."""

    kind: OperationKind
    paths: list[Path]

    # Album groups: directory key → list of paths (for album operations)
    album_groups: dict[str, list[Path]] = field(default_factory=dict)

    # For apply_constant: constant dB gain to apply (e.g. +3.0 or -6.0)
    constant_db: float = 0.0

    # Target volume for analysis (dB, default 89)
    target_db: float = 89.0

    # Analyze max-amplitude only (skip gain computation details).
    max_amp_only: bool = False

    # Tag write mode
    tag_mode: str = "apev2"
    stored_tag_policy: StoredTagPolicy = "auto"

    # Gain writer options
    wrap_gain: bool = False
    preserve_dates: bool = False
    force_apply_normalization: bool = True
    apply_zero_step: bool = False


@dataclass
class FileResult:
    """Analysis/modification result for a single file."""

    path: Path
    ok: bool
    error_msg: str = ""

    # ReplayGain analysis results
    volume_db: float | None = None
    track_gain_db: float | None = None
    album_gain_db: float | None = None
    max_amplitude: float | None = None
    min_gain_field: int | None = None
    max_gain_field: int | None = None

    # Clipping
    clipping: bool = False
    clip_track: float | None = None
    album_volume_db: float | None = None
    clip_album: float | None = None


@dataclass
class WorkerResult:
    """Summary of a completed worker operation."""

    kind: OperationKind
    total: int
    succeeded: int
    failed: int
    cancelled: bool = False
    error_msg: str = ""
