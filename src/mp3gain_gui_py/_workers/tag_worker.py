"""TagWorker - background tag delete worker (no Qt)."""

from __future__ import annotations

import os
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from typing import TYPE_CHECKING, TypeVar

from .process_tasks import delete_tags_file_task
from .types import FileResult, WorkerBridgeLike, WorkerRequest, WorkerResult

if TYPE_CHECKING:
    from pathlib import Path

_FutureResultT = TypeVar("_FutureResultT")


class TagWorker:
    """Delete ReplayGain tags from a list of MP3 files."""

    _request: WorkerRequest
    _bridge: WorkerBridgeLike

    def __init__(self, request: WorkerRequest, bridge: WorkerBridgeLike) -> None:
        self._request = request
        self._bridge = bridge

    @staticmethod
    def _max_workers(total: int) -> int:
        return min(max(1, os.cpu_count() or 1), max(1, total))

    @staticmethod
    def _cancel_pending_futures(
        futures: dict[Future[_FutureResultT], Path],
    ) -> None:
        for future in futures:
            if not future.done():
                _ = future.cancel()

    def run(self) -> None:
        req = self._request
        paths = req.paths
        total = len(paths)
        succeeded = 0
        failed = 0
        cancelled = False
        processed = 0

        futures: dict[Future[FileResult], Path] = {}
        with ProcessPoolExecutor(max_workers=self._max_workers(total)) as executor:
            for path in paths:
                if self._bridge.is_cancelled:
                    cancelled = True
                    break
                self._bridge.relay_file_started(path)
                future = executor.submit(
                    delete_tags_file_task,
                    str(path),
                    tag_mode=req.tag_mode,
                )
                futures[future] = path

            for future in as_completed(futures):
                if self._bridge.is_cancelled and not cancelled:
                    cancelled = True
                    self._cancel_pending_futures(futures)
                path = futures[future]
                if future.cancelled():
                    continue
                try:
                    result = future.result()
                except Exception as exc:  # pragma: no cover - defensive
                    result = FileResult(path=path, ok=False, error_msg=str(exc))
                if result.ok:
                    succeeded += 1
                else:
                    failed += 1
                processed += 1
                self._bridge.relay_file_done(result)
                self._bridge.relay_progress(processed, total)

        self._bridge.relay_all_done(
            WorkerResult(
                kind=req.kind,
                total=total,
                succeeded=succeeded,
                failed=failed,
                cancelled=cancelled,
            )
        )
