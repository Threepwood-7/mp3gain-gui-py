"""High-level legacy-compatible processor facade.

Legacy Pointers:
- LEGACY_PTR:EXACT_PROCESSOR_APPLY
- LEGACY_PTR:EXACT_PROCESSOR_UNDO
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .._c_backend import (
    CBackendError,
    CBackendPathError,
    CBackendUnavailable,
    get_backend,
)
from .._engine.pcm_reader import decode_to_stereo_chunks, read_mp3_info
from .._engine.replaygain import GainAnalyzer
from .._mp3.file_info import scan_file, scan_max_amplitude
from .._mp3.frame_parser import (
    FrameHeader,
    find_next_frame,
    has_xing_or_info_tag,
    parse_frame_header,
)
from .._mp3.gain_writer import apply_gain_change, undo_gain_change
from .._tags.reader import TagData, read_tags
from .._tags.writer import delete_tags, delete_tags_for_format, write_tags
from .math import db_to_legacy_steps

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
        self._backend = None
        self._backend_error = ""
        if os.environ.get("MP3GAIN_GUI_PY_DISABLE_C_BACKEND", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            return
        try:
            self._backend = get_backend(auto_build=True)
        except CBackendUnavailable as exc:
            self._backend = None
            self._backend_error = str(exc)

    def analyze_track_gain_db(self, path: Path) -> float:
        gain_db, _used_ascii_alias = self.analyze_track_gain_db_with_fallback(path)
        return gain_db

    def analyze_track_gain_db_with_fallback(self, path: Path) -> tuple[float, bool]:
        gain_db, _max_amp, used_ascii_alias = self.analyze_track_gain_and_peak_with_fallback(path)
        return gain_db, used_ascii_alias

    def analyze_track_gain_and_peak_with_fallback(self, path: Path) -> tuple[float, float, bool]:
        try:
            gain_db, max_amp = self._analyze_track_gain_and_peak_impl(path)
            return gain_db, max_amp, False
        except Exception:
            if not self._contains_non_ascii(path):
                raise
        with tempfile.TemporaryDirectory(prefix="mp3gain_ascii_") as temp_dir:
            alias_path = Path(temp_dir) / "input.mp3"
            shutil.copyfile(path, alias_path)
            gain_db, max_amp = self._analyze_track_gain_and_peak_impl(alias_path)
            return gain_db, max_amp, True

    def _analyze_track_gain_db_impl(self, path: Path) -> float:
        gain_db, _max_amp = self._analyze_track_gain_and_peak_impl(path)
        return gain_db

    def _analyze_track_gain_and_peak_impl(self, path: Path) -> tuple[float, float]:
        if self._backend is not None:
            try:
                return self._backend.analyze_track_gain_and_peak(path)
            except (CBackendPathError, CBackendError):
                pass
        sample_rate, _channels = read_mp3_info(path)
        analyzer = GainAnalyzer(sample_rate)
        max_amp = 0.0
        for _sr, left, right in decode_to_stereo_chunks(path, chunk_frames=8192):
            analyzer.analyze_samples(left, right, len(left))
            left_peak = max((abs(value) for value in left), default=0.0)
            right_peak = max((abs(value) for value in right), default=0.0)
            chunk_peak = left_peak if left_peak >= right_peak else right_peak
            if chunk_peak > max_amp:
                max_amp = chunk_peak
        return analyzer.get_title_gain(), max_amp

    @staticmethod
    def _contains_non_ascii(path: Path) -> bool:
        text = str(path)
        return any(ord(ch) > 127 for ch in text)

    def analyze_max_amplitude(self, path: Path) -> float:
        return scan_max_amplitude(path)

    def analyze_minmax_gain(self, path: Path) -> tuple[int, int]:
        return scan_file(path)

    def analyze_track_metrics(
        self,
        path: Path,
        *,
        include_gain: bool = True,
    ) -> tuple[float, float, int, int]:
        if include_gain:
            gain_db, max_amp, _used_ascii_alias = self.analyze_track_gain_and_peak_with_fallback(path)
        else:
            gain_db = 0.0
            max_amp = self.analyze_max_amplitude(path)
        min_gain, max_gain = self.analyze_minmax_gain(path)
        return gain_db, max_amp, min_gain, max_gain

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

        gain_sum = 0.0
        min_gain = 255
        max_gain = 0
        max_amp = 0.0

        for path in paths:
            track_gain, track_max_amp, track_min_gain, track_max_gain = self.analyze_track_metrics(
                path,
                include_gain=include_gain,
            )
            gain_sum += track_gain
            if track_min_gain < min_gain:
                min_gain = track_min_gain
            if track_max_gain > max_gain:
                max_gain = track_max_gain
            if track_max_amp > max_amp:
                max_amp = track_max_amp

        album_gain = gain_sum / float(len(paths)) if include_gain else 0.0
        if min_gain > max_gain:
            return album_gain, 0, 0, max_amp
        return album_gain, min_gain, max_gain, max_amp

    def compute_autoclip_steps(self, requested_steps: int, *, min_gain: int, max_gain: int) -> int:
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

        if self._backend is not None:
            try:
                self._backend.apply_gain_file(
                    path,
                    left_gain_steps=left_steps,
                    right_gain_steps=right,
                    wrap_gain=options.wrap_gain,
                    preserve_timestamp=options.preserve_timestamp,
                    use_temp_file=options.use_temp_file,
                )
                return LegacyCommandResult(exit_code=0, changed=True)
            except (CBackendPathError, CBackendError):
                # Narrow compatibility fallback for unsupported path/toolchain cases.
                pass

        apply_gain_change(
            path,
            left_steps,
            gain_delta_right=right,
            wrap=options.wrap_gain,
            preserve_timestamp=options.preserve_timestamp,
            use_temp_file=options.use_temp_file,
        )
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
        header = self._read_first_audio_header(path)
        if header is None:
            return LegacyCommandResult(exit_code=1, changed=False, message="No MPEG audio frame found")
        if header.num_channels == 1:
            return LegacyCommandResult(exit_code=1, changed=False, message="Single-channel gain unsupported for mono")
        # Legacy mp3gain rejects single-channel edits for joint-stereo files.
        if header.channel_mode == 0x01:
            return LegacyCommandResult(
                exit_code=1,
                changed=False,
                message="Single-channel gain unsupported for joint stereo",
            )
        if channel_index not in {0, 1}:
            return LegacyCommandResult(exit_code=1, changed=False, message="Channel index must be 0 or 1")

        left_steps = steps if channel_index == 0 else 0
        right_steps = steps if channel_index == 1 else 0
        return self.apply_steps(
            path,
            left_steps=left_steps,
            right_steps=right_steps,
            options=options,
        )

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
            use_temp_file=options.use_temp_file,
        )
        return LegacyCommandResult(exit_code=0, changed=True)

    def delete_mp3gain_tags(
        self,
        path: Path,
        *,
        tag_format: Literal["apev2", "id3"] | None = None,
    ) -> LegacyCommandResult:
        if self._backend is not None:
            try:
                self._backend.delete_tags(
                    path,
                    tag_format=tag_format,
                    preserve_timestamp=False,
                )
                return LegacyCommandResult(exit_code=0, changed=True)
            except (CBackendPathError, CBackendError):
                pass

        if tag_format is None:
            delete_tags(path)
        else:
            delete_tags_for_format(path, tag_format=tag_format)
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
        if self._backend is not None:
            try:
                self._backend.write_tags(
                    path,
                    payload,
                    tag_format=tag_format,
                    preserve_timestamp=False,
                )
                return
            except (CBackendPathError, CBackendError):
                pass
        write_tags(path, payload, tag_format=tag_format)

    def _read_first_audio_header(self, path: Path) -> FrameHeader | None:
        data = path.read_bytes()
        pos = 0
        if data[:3] == b"ID3" and len(data) >= 10:
            id3_size = (
                (data[9] & 0x7F)
                | ((data[8] & 0x7F) << 7)
                | ((data[7] & 0x7F) << 14)
                | ((data[6] & 0x7F) << 21)
            )
            pos = 10 + id3_size

        first_audio_frame = True
        while True:
            pos = find_next_frame(data, pos)
            if pos < 0:
                return None
            header = parse_frame_header(data, pos)
            if header is None:
                pos += 1
                continue
            if pos + header.frame_size_bytes > len(data):
                return None
            if first_audio_frame:
                first_audio_frame = False
                if has_xing_or_info_tag(data, pos, header):
                    pos += header.frame_size_bytes
                    continue
            return header
