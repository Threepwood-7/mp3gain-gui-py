"""TagWorker — background tag write/delete worker (no Qt)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._legacy_exact.processor import LegacyExactProcessor
from .types import FileResult, WorkerRequest, WorkerResult

if TYPE_CHECKING:
    from pathlib import Path

    from .worker_bridge import WorkerBridge


class TagWorker:
    """Delete ReplayGain tags from a list of MP3 files."""

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
        try:
            result = self._processor.delete_mp3gain_tags(path)
            if result.exit_code != 0:
                return FileResult(path=path, ok=False, error_msg=result.message)
        except Exception as exc:
            return FileResult(path=path, ok=False, error_msg=str(exc))
        return FileResult(path=path, ok=True)
