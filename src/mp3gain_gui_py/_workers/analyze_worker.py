"""AnalyzeWorker — background ReplayGain analysis (no Qt)."""

from __future__ import annotations

import math
from contextlib import suppress
from typing import TYPE_CHECKING

from .._legacy_exact.processor import LegacyExactProcessor
from .._tags.reader import read_tags
from .types import FileResult, WorkerRequest, WorkerResult

if TYPE_CHECKING:
    from pathlib import Path

    from .worker_bridge import WorkerBridge

class AnalyzeWorker:
    """Run ReplayGain analysis on a list of paths.

    For ``kind="track_analyze"`` each file is analyzed independently.
    For ``kind="album_analyze"`` album gain is accumulated across each group
    of files sharing a common parent directory.
    """

    def __init__(self, request: WorkerRequest, bridge: WorkerBridge) -> None:
        self._request = request
        self._bridge = bridge
        self._processor = LegacyExactProcessor()

    def run(self) -> None:
        req = self._request
        paths = req.paths
        total = len(paths)
        succeeded = 0
        failed = 0
        cancelled = False

        if req.kind == "album_analyze":
            self._run_album(paths, total)
            return

        # Track-only analysis
        for i, path in enumerate(paths):
            if self._bridge.is_cancelled:
                cancelled = True
                break
            self._bridge._relay_file_started(path)
            result = self._analyze_track(path, req.target_db)
            if result.ok:
                succeeded += 1
            else:
                failed += 1
            self._bridge._relay_file_done(result)
            self._bridge._relay_progress(i + 1, total)

        self._bridge._relay_all_done(
            WorkerResult(
                kind=req.kind,
                total=total,
                succeeded=succeeded,
                failed=failed,
                cancelled=cancelled,
            )
        )

    def _run_album(self, paths: list[Path], total: int) -> None:
        req = self._request
        succeeded = 0
        failed = 0
        cancelled = False

        # Group by parent directory
        groups: dict[str, list[Path]] = {}
        for p in paths:
            groups.setdefault(str(p.parent), []).append(p)

        # Per-group album accumulation
        processed = 0

        for group_paths in groups.values():
            album_raw_db: float | None = None
            with suppress(Exception):
                album_raw_db, _album_min_gain, _album_max_gain, _album_max_amp = (
                    self._processor.analyze_album_metrics(
                        group_paths,
                        include_gain=not req.max_amp_only,
                    )
                )

            for path in group_paths:
                if self._bridge.is_cancelled:
                    cancelled = True
                    break
                self._bridge._relay_file_started(path)
                result = self._analyze_track(path, req.target_db)
                if result.ok and album_raw_db is not None:
                    album_gain_db = album_raw_db
                    album_volume_db = req.target_db - album_raw_db
                    max_amp = result.max_amplitude or 0.0
                    clip_album = max_amp * _db_to_linear(album_gain_db) if max_amp else None
                    result = FileResult(
                        path=result.path,
                        ok=result.ok,
                        error_msg=result.error_msg,
                        volume_db=result.volume_db,
                        track_gain_db=result.track_gain_db,
                        album_gain_db=album_gain_db,
                        max_amplitude=result.max_amplitude,
                        min_gain_field=result.min_gain_field,
                        max_gain_field=result.max_gain_field,
                        clipping=result.clipping,
                        clip_track=result.clip_track,
                        album_volume_db=album_volume_db,
                        clip_album=clip_album,
                    )
                processed += 1
                if result.ok:
                    succeeded += 1
                else:
                    failed += 1
                self._bridge._relay_file_done(result)
                self._bridge._relay_progress(processed, total)
            if cancelled:
                break

        self._bridge._relay_all_done(
            WorkerResult(
                kind=req.kind,
                total=total,
                succeeded=succeeded,
                failed=failed,
                cancelled=cancelled,
            )
        )

    def _analyze_track(self, path: Path, target_db: float) -> FileResult:
        """Full per-track analysis without album accumulation."""
        policy = self._request.stored_tag_policy
        if policy == "check_only":
            tagged = self._analyze_track_from_tags(path, target_db)
            if tagged is not None:
                return tagged
            return FileResult(path=path, ok=True, volume_db=target_db, track_gain_db=0.0)
        if policy == "auto":
            tagged = self._analyze_track_from_tags(path, target_db, allow_empty=True)
            if tagged is not None:
                return tagged

        sr = 44100
        del sr
        try:
            raw_db, max_amp, min_g, max_g = self._processor.analyze_track_metrics(
                path,
                include_gain=not self._request.max_amp_only,
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

    def _analyze_track_from_tags(
        self,
        path: Path,
        target_db: float,
        *,
        allow_empty: bool = False,
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

def _db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)
