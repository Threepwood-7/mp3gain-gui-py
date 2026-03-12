"""High-level legacy-compatible processor facade.

Legacy Pointers:
- LEGACY_PTR:EXACT_PROCESSOR_APPLY
- LEGACY_PTR:EXACT_PROCESSOR_UNDO
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .._c_backend import CBackendError, get_backend
from .._tags.reader import TagData
from .math import db_to_legacy_steps

if TYPE_CHECKING:
    from pathlib import Path

StoredTagPolicy = Literal["auto", "skip", "recalc", "check_only"]


@dataclass(frozen=True)
class LegacyCompatOptions:
    """Options controlling legacy-compatible file mutation behavior."""

    wrap_gain: bool = False
    auto_clip: bool = False
    preserve_timestamp: bool = False
    use_temp_file: bool = True
    tag_format: Literal["apev2", "id3"] = "apev2"
    stored_tag_policy: StoredTagPolicy = "auto"


@dataclass(frozen=True)
class LegacyCommandResult:
    """Result object for legacy processor operations."""

    exit_code: int
    changed: bool
    message: str = ""


class LegacyExactProcessor:
    """Single source of truth for legacy-compatible analyze/apply operations."""

    def __init__(self) -> None:
        self._backend = get_backend(auto_build=True)

    def analyze_track_gain_db(self, path: Path) -> float:
        gain_db, _used_ascii_alias = self.analyze_track_gain_db_with_fallback(path)
        return gain_db

    def analyze_track_gain_db_with_fallback(self, path: Path) -> tuple[float, bool]:
        gain_db, _max_amp, _min_gain, _max_gain = self._backend.scan_track_metrics(
            path, include_gain=True
        )
        return gain_db, False

    def analyze_track_gain_and_peak_with_fallback(
        self, path: Path
    ) -> tuple[float, float, bool]:
        gain_db, max_amp, _min_gain, _max_gain = self._backend.scan_track_metrics(
            path, include_gain=True
        )
        return gain_db, max_amp, False

    def analyze_max_amplitude(self, path: Path) -> float:
        _gain_db, max_amp, _min_gain, _max_gain = self._backend.scan_track_metrics(
            path, include_gain=False
        )
        return max_amp

    def analyze_minmax_gain(self, path: Path) -> tuple[int, int]:
        _gain_db, _max_amp, min_gain, max_gain = self._backend.scan_track_metrics(
            path, include_gain=False
        )
        return min_gain, max_gain

    def analyze_track_metrics(
        self,
        path: Path,
        *,
        include_gain: bool = True,
    ) -> tuple[float, float, int, int]:
        return self._backend.scan_track_metrics(path, include_gain=include_gain)

    def analyze_album_gain_db(self, paths: list[Path]) -> float:
        if not paths:
            return 0.0
        values = [self.analyze_track_gain_db(path) for path in paths]
        return sum(values) / float(len(values))

    def analyze_album_minmax_gain(self, paths: list[Path]) -> tuple[int, int]:
        if not paths:
            return 0, 0
        mins: list[int] = []
        maxes: list[int] = []
        for path in paths:
            min_gain, max_gain = self.analyze_minmax_gain(path)
            mins.append(min_gain)
            maxes.append(max_gain)
        return min(mins), max(maxes)

    def analyze_album_metrics(
        self,
        paths: list[Path],
        *,
        include_gain: bool = True,
    ) -> tuple[float, int, int, float]:
        if not paths:
            return 0.0, 0, 0, 0.0

        min_gain = 255
        max_gain = 0
        max_amp = 0.0

        if include_gain:
            self._backend.begin_album_scan()

        for path in paths:
            _track_gain, track_max_amp, track_min_gain, track_max_gain = (
                self.analyze_track_metrics(
                    path,
                    include_gain=include_gain,
                )
            )
            if track_min_gain < min_gain:
                min_gain = track_min_gain
            if track_max_gain > max_gain:
                max_gain = track_max_gain
            if track_max_amp > max_amp:
                max_amp = track_max_amp

        album_gain = self._backend.finish_album_scan() if include_gain else 0.0
        if min_gain > max_gain:
            return album_gain, 0, 0, max_amp
        return album_gain, min_gain, max_gain, max_amp

    def compute_autoclip_steps(
        self, requested_steps: int, *, min_gain: int, max_gain: int
    ) -> int:
        """Clamp requested step deltas to avoid legacy global_gain clipping."""
        if requested_steps > 0:
            return min(requested_steps, 255 - max_gain)
        if requested_steps < 0:
            return max(requested_steps, -min_gain)
        return 0

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
        try:
            self._backend.apply_gain_file(
                path,
                left_gain_steps=left_steps,
                right_gain_steps=right,
                wrap_gain=options.wrap_gain,
                preserve_timestamp=options.preserve_timestamp,
                use_temp_file=options.use_temp_file,
            )
        except CBackendError as exc:
            return LegacyCommandResult(exit_code=1, changed=False, message=str(exc))
        return LegacyCommandResult(exit_code=0, changed=True)

    def apply_direct_gain_steps(
        self,
        path: Path,
        *,
        steps: int,
        options: LegacyCompatOptions,
    ) -> LegacyCommandResult:
        return self.apply_steps(path, left_steps=steps, options=options)

    def apply_single_channel_steps(
        self,
        path: Path,
        *,
        channel_index: int,
        steps: int,
        options: LegacyCompatOptions,
    ) -> LegacyCommandResult:
        if channel_index not in {0, 1}:
            return LegacyCommandResult(
                exit_code=1, changed=False, message="Channel index must be 0 or 1"
            )
        left_steps = steps if channel_index == 0 else 0
        right_steps = steps if channel_index == 1 else 0
        return self.apply_steps(
            path,
            left_steps=left_steps,
            right_steps=right_steps,
            options=options,
        )

    def read_replaygain_tags(self, path: Path) -> TagData:
        return self._backend.read_tags(path)

    def write_replaygain_tagdata(
        self,
        path: Path,
        tags: TagData,
        *,
        tag_format: Literal["apev2", "id3"],
        preserve_timestamp: bool,
    ) -> None:
        self._backend.write_tags(
            path,
            tags,
            tag_format=tag_format,
            preserve_timestamp=preserve_timestamp,
        )

    def undo(self, path: Path, *, options: LegacyCompatOptions) -> LegacyCommandResult:
        """Undo a prior apply operation using MP3GAIN_UNDO metadata.

        Legacy pointer: LEGACY_PTR:EXACT_PROCESSOR_UNDO.
        """
        tags = self.read_replaygain_tags(path)
        if not tags.has_undo:
            return LegacyCommandResult(
                exit_code=1, changed=False, message="Missing MP3GAIN_UNDO"
            )
        undo_left = tags.undo_left if tags.undo_left is not None else 0
        undo_right = tags.undo_right if tags.undo_right is not None else 0
        if undo_left == 0 and undo_right == 0:
            return LegacyCommandResult(exit_code=0, changed=False)
        return self.apply_steps(
            path,
            left_steps=undo_left,
            right_steps=undo_right,
            options=options,
        )

    def delete_mp3gain_tags(
        self,
        path: Path,
        *,
        tag_format: Literal["apev2", "id3"] | None = None,
    ) -> LegacyCommandResult:
        try:
            self._backend.delete_tags(
                path,
                tag_format=tag_format,
                preserve_timestamp=False,
            )
        except CBackendError as exc:
            return LegacyCommandResult(exit_code=1, changed=False, message=str(exc))
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
        payload = TagData(
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
        )
        self.write_replaygain_tagdata(
            path,
            payload,
            tag_format=tag_format,
            preserve_timestamp=False,
        )
