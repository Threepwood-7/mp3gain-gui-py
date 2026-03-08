"""GainWorker — background gain application worker (no Qt)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .._mp3.gain_writer import apply_gain_change, undo_gain_change
from .types import FileResult, WorkerRequest, WorkerResult

if TYPE_CHECKING:
    from .worker_bridge import WorkerBridge


class GainWorker:
    """Apply gain changes to a list of MP3 files.

    Supports: apply_track, apply_album, apply_constant, undo.
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

        for i, path in enumerate(paths):
            if self._bridge.is_cancelled:
                cancelled = True
                break

            self._bridge._relay_file_started(path)
            result = self._process_file(path)
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

    def _process_file(self, path: Path) -> FileResult:
        req = self._request
        try:
            if req.kind == "undo":
                undo_gain_change(
                    path,
                    wrap=req.wrap_gain,
                    preserve_timestamp=req.preserve_dates,
                )
            else:
                gain_db = self._gain_for(path)
                steps = round(gain_db / 1.5)
                apply_gain_change(
                    path,
                    path,
                    steps,
                    wrap=req.wrap_gain,
                    preserve_timestamp=req.preserve_dates,
                )
        except Exception as exc:
            return FileResult(path=path, ok=False, error_msg=str(exc))
        return FileResult(path=path, ok=True)

    def _gain_for(self, path: Path) -> float:
        req = self._request
        if req.kind == "apply_constant":
            return req.constant_db
        if req.kind == "apply_track":
            # track_gain_db stored in file entry is pre-computed
            # (req.album_groups stores {path_str: gain_db} for per-file gains)
            per_file = req.album_groups.get(str(path))
            if per_file:
                return float(per_file[0]) if per_file else 0.0  # type: ignore[arg-type]
            return 0.0
        if req.kind == "apply_album":
            per_group = req.album_groups.get(str(path.parent))
            if per_group:
                return float(per_group[0]) if per_group else 0.0  # type: ignore[arg-type]
            return 0.0
        return 0.0


