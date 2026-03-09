"""AnalyzeWorker — background ReplayGain analysis (no Qt)."""

from __future__ import annotations

import math
from contextlib import suppress
from typing import TYPE_CHECKING

from .._engine.pcm_reader import decode_to_stereo_chunks, read_mp3_info
from .._engine.replaygain import GainAnalyzer
from .._mp3.file_info import scan_file, scan_max_amplitude
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
        results_by_path: dict[Path, FileResult] = {}
        processed = 0

        for group_paths in groups.values():
            # Determine common sample rate (first file wins; all should match)
            sr = 44100
            with suppress(Exception):
                sr, _ = read_mp3_info(group_paths[0])

            ga = GainAnalyzer(sr)

            for path in group_paths:
                if self._bridge.is_cancelled:
                    cancelled = True
                    break
                self._bridge._relay_file_started(path)
                result = self._analyze_track_with_ga(path, req.target_db, ga)
                results_by_path[path] = result
                processed += 1
                self._bridge._relay_progress(processed, total)
            if cancelled:
                break

            # Album gain available after all tracks in group
            try:
                album_raw_db = ga.get_album_gain()
            except Exception:
                album_raw_db = None  # type: ignore[assignment]

            for path in group_paths:
                r = results_by_path.get(path)
                if r is None or not r.ok:
                    continue
                if album_raw_db is not None:
                    album_gain_db = album_raw_db
                    album_volume_db = req.target_db - album_raw_db
                    max_amp = r.max_amplitude or 0.0
                    clip_album = max_amp * _db_to_linear(album_gain_db) if max_amp else None
                    r = FileResult(
                        path=r.path,
                        ok=r.ok,
                        error_msg=r.error_msg,
                        volume_db=r.volume_db,
                        track_gain_db=r.track_gain_db,
                        album_gain_db=album_gain_db,
                        max_amplitude=r.max_amplitude,
                        min_gain_field=r.min_gain_field,
                        max_gain_field=r.max_gain_field,
                        clipping=r.clipping,
                        clip_track=r.clip_track,
                        album_volume_db=album_volume_db,
                        clip_album=clip_album,
                    )
                self._bridge._relay_file_done(r)
                if r.ok:
                    succeeded += 1
                else:
                    failed += 1

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
        sr = 44100
        try:
            sr, _ = read_mp3_info(path)
        except Exception as exc:
            return FileResult(path=path, ok=False, error_msg=str(exc))

        ga = GainAnalyzer(sr)
        return self._analyze_track_with_ga(path, target_db, ga)

    def _analyze_track_with_ga(
        self, path: Path, target_db: float, ga: GainAnalyzer
    ) -> FileResult:
        """Feed file into existing GainAnalyzer; return per-track result."""
        try:
            for _, left, right in decode_to_stereo_chunks(path):
                ga.analyze_samples(left, right, len(left))

            raw_db = ga.get_title_gain()
            track_gain_db = raw_db
            volume_db = target_db - raw_db

            min_g, max_g = scan_file(path)
            max_amp = scan_max_amplitude(path)

            # Clipping after applying the recommended track gain.
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


def _db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)
