"""High-level legacy-compatible processor facade.

Legacy Pointers:
- LEGACY_PTR:EXACT_PROCESSOR_APPLY
- LEGACY_PTR:EXACT_PROCESSOR_UNDO
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .._engine.pcm_reader import decode_to_stereo_chunks, read_mp3_info
from .._engine.replaygain import GainAnalyzer
from .._mp3.file_info import scan_file, scan_max_amplitude
from .._mp3.gain_writer import apply_gain_change, undo_gain_change
from .._tags.reader import TagData, read_tags
from .._tags.writer import write_tags
from .math import db_to_legacy_steps


@dataclass(frozen=True)
class LegacyCompatOptions:
    """Options controlling legacy-compatible file mutation behavior."""

    wrap_gain: bool = False
    preserve_timestamp: bool = False
    tag_format: Literal["apev2", "id3"] = "apev2"


@dataclass(frozen=True)
class LegacyCommandResult:
    """Result object for legacy processor operations."""

    exit_code: int
    changed: bool
    message: str = ""


class LegacyExactProcessor:
    """Single source of truth for legacy-compatible analyze/apply operations."""

    def analyze_track_gain_db(self, path: Path) -> float:
        sample_rate, _channels = read_mp3_info(path)
        analyzer = GainAnalyzer(sample_rate)
        for _sr, left, right in decode_to_stereo_chunks(path, chunk_frames=8192):
            analyzer.analyze_samples(left, right, len(left))
        return analyzer.get_title_gain()

    def analyze_max_amplitude(self, path: Path) -> float:
        return scan_max_amplitude(path)

    def analyze_minmax_gain(self, path: Path) -> tuple[int, int]:
        return scan_file(path)

    def apply_db_gain(
        self,
        path: Path,
        gain_db: float,
        *,
        options: LegacyCompatOptions,
        right_gain_db: float | None = None,
        mp3_gain_mod: int = 0,
    ) -> LegacyCommandResult:
        left_steps = db_to_legacy_steps(gain_db, mp3_gain_mod=mp3_gain_mod)
        right_steps = (
            db_to_legacy_steps(right_gain_db, mp3_gain_mod=mp3_gain_mod)
            if right_gain_db is not None
            else left_steps
        )
        return self.apply_steps(
            path,
            left_steps=left_steps,
            right_steps=right_steps,
            options=options,
        )

    def apply_steps(
        self,
        path: Path,
        *,
        left_steps: int,
        right_steps: int | None = None,
        options: LegacyCompatOptions,
    ) -> LegacyCommandResult:
        """Apply explicit MP3 gain steps.

        Legacy pointer: LEGACY_PTR:EXACT_PROCESSOR_APPLY.
        """
        right = right_steps if right_steps is not None else left_steps
        if left_steps == 0 and right == 0:
            return LegacyCommandResult(exit_code=0, changed=False)

        apply_gain_change(
            path,
            left_steps,
            gain_delta_right=right,
            wrap=options.wrap_gain,
            preserve_timestamp=options.preserve_timestamp,
        )
        return LegacyCommandResult(exit_code=0, changed=True)

    def undo(self, path: Path, *, options: LegacyCompatOptions) -> LegacyCommandResult:
        """Undo a prior apply operation using MP3GAIN_UNDO metadata.

        Legacy pointer: LEGACY_PTR:EXACT_PROCESSOR_UNDO.
        """
        tags = read_tags(path)
        if not tags.has_undo:
            return LegacyCommandResult(exit_code=1, changed=False, message="Missing MP3GAIN_UNDO")
        undo_gain_change(
            path,
            tags.undo_tag_value,
            wrap=options.wrap_gain,
            preserve_timestamp=options.preserve_timestamp,
        )
        return LegacyCommandResult(exit_code=0, changed=True)

    def write_replaygain_tags(
        self,
        path: Path,
        *,
        track_gain_db: float,
        track_peak: float,
        undo_left: int,
        undo_right: int,
        undo_mode: str,
        min_gain: int,
        max_gain: int,
        album_gain_db: float | None = None,
        album_peak: float | None = None,
        album_min_gain: int | None = None,
        album_max_gain: int | None = None,
        tag_format: Literal["apev2", "id3"] = "apev2",
    ) -> None:
        write_tags(
            path,
            TagData(
                tag_format=tag_format,
                track_gain_db=track_gain_db,
                track_peak=track_peak,
                album_gain_db=album_gain_db,
                album_peak=album_peak,
                undo_left=undo_left,
                undo_right=undo_right,
                undo_mode=undo_mode,
                min_gain=min_gain,
                max_gain=max_gain,
                album_min_gain=album_min_gain,
                album_max_gain=album_max_gain,
            ),
            tag_format=tag_format,
        )
