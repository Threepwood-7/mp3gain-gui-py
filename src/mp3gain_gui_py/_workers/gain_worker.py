"""GainWorker — background gain application worker (no Qt)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._legacy_exact.math import db_to_legacy_steps
from .._mp3.gain_writer import apply_gain_change, undo_gain_change
from .._tags.reader import read_tags
from .types import FileResult, WorkerRequest, WorkerResult

if TYPE_CHECKING:
    from pathlib import Path

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
                undo_tag = self._undo_tag_for(path)
                undo_gain_change(
                    path,
                    undo_tag,
                    wrap=req.wrap_gain,
                    preserve_timestamp=req.preserve_dates,
                )
            else:
                gain_db = self._gain_for(path)
                steps = db_to_legacy_steps(gain_db)
                apply_gain_change(
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
            tag_data = read_tags(path)
            return tag_data.track_gain_db if tag_data.track_gain_db is not None else 0.0
        if req.kind == "apply_album":
            tag_data = read_tags(path)
            if tag_data.album_gain_db is not None:
                return tag_data.album_gain_db
            if tag_data.track_gain_db is not None:
                return tag_data.track_gain_db
            return 0.0
        return 0.0

    def _undo_tag_for(self, path: Path) -> str:
        tag_data = read_tags(path)
        if tag_data.has_undo:
            return tag_data.undo_tag_value
        raise ValueError(f"Missing MP3GAIN_UNDO tag in {path}")
