"""GainWorker - background gain application worker (no Qt)."""

from __future__ import annotations

import os
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from .._legacy_exact.math import db_to_legacy_steps
from .process_tasks import album_group_gain_task, gain_file_task
from .types import FileResult, WorkerBridgeLike, WorkerRequest, WorkerResult

if TYPE_CHECKING:
    from collections.abc import Iterable

_LEGACY_TARGET_DB = 89.0
_FutureResultT = TypeVar("_FutureResultT")


class GainWorker:
    """Apply gain changes to a list of MP3 files."""

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
        futures: Iterable[Future[_FutureResultT]],
    ) -> None:
        for future in futures:
            if not future.done():
                _ = future.cancel()

    @staticmethod
    def _group_by_parent(paths: list[Path]) -> dict[str, list[Path]]:
        groups: dict[str, list[Path]] = {}
        for path in paths:
            groups.setdefault(str(path.parent), []).append(path)
        return groups

    def _compute_forced_album_steps(
        self, *, req: WorkerRequest, paths: list[Path]
    ) -> tuple[dict[Path, int], bool]:
        groups = req.album_groups if req.album_groups else self._group_by_parent(paths)
        group_items = list(groups.values())
        if not group_items:
            return {}, False

        cancelled = False
        final_steps_by_path: dict[Path, int] = {}
        step_offset = db_to_legacy_steps(req.target_db - _LEGACY_TARGET_DB)

        group_futures: dict[
            Future[tuple[tuple[str, ...], float | None]], tuple[Path, ...]
        ] = {}
        with ProcessPoolExecutor(
            max_workers=self._max_workers(len(group_items))
        ) as group_executor:
            for group_paths in group_items:
                if self._bridge.is_cancelled:
                    cancelled = True
                    break
                path_texts = tuple(str(path) for path in group_paths)
                future = group_executor.submit(
                    album_group_gain_task,
                    path_texts,
                    max_amp_only=False,
                )
                group_futures[future] = tuple(group_paths)

            for future in as_completed(group_futures):
                if self._bridge.is_cancelled and not cancelled:
                    cancelled = True
                    self._cancel_pending_futures(group_futures.keys())
                if future.cancelled():
                    continue
                try:
                    path_texts, album_raw_db = future.result()
                except Exception:
                    continue
                if album_raw_db is None:
                    continue
                analyzed_steps = db_to_legacy_steps(float(album_raw_db))
                final_steps = analyzed_steps + step_offset
                for path_text in path_texts:
                    final_steps_by_path[Path(path_text)] = final_steps

        return final_steps_by_path, cancelled

    def run(self) -> None:
        req = self._request
        paths = req.paths
        total = len(paths)
        succeeded = 0
        failed = 0
        cancelled = False
        processed = 0

        forced_album_steps: dict[Path, int] = {}
        if req.kind == "apply_album" and req.force_apply_normalization:
            forced_album_steps, cancelled = self._compute_forced_album_steps(
                req=req,
                paths=paths,
            )

        futures: dict[Future[FileResult], Path] = {}
        with ProcessPoolExecutor(max_workers=self._max_workers(total)) as executor:
            for path in paths:
                if cancelled or self._bridge.is_cancelled:
                    cancelled = True
                    break
                self._bridge.relay_file_started(path)
                future = executor.submit(
                    gain_file_task,
                    req.kind,
                    str(path),
                    constant_db=req.constant_db,
                    wrap_gain=req.wrap_gain,
                    preserve_dates=req.preserve_dates,
                    target_db=req.target_db,
                    force_apply_normalization=req.force_apply_normalization,
                    apply_zero_step=req.apply_zero_step,
                    forced_steps=forced_album_steps.get(path),
                )
                futures[future] = path

            for future in as_completed(futures):
                if self._bridge.is_cancelled and not cancelled:
                    cancelled = True
                    self._cancel_pending_futures(futures.keys())
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
