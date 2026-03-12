"""AnalyzeWorker - background ReplayGain analysis (no Qt)."""

from __future__ import annotations

import math
import os
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

from .process_tasks import album_group_gain_task, analyze_file_task
from .types import FileResult, WorkerRequest, WorkerResult

if TYPE_CHECKING:
    from .worker_bridge import WorkerBridge


class AnalyzeWorker:
    """Run ReplayGain analysis on a list of paths."""

    def __init__(self, request: WorkerRequest, bridge: WorkerBridge) -> None:
        self._request = request
        self._bridge = bridge

    def run(self) -> None:
        req = self._request
        paths = req.paths
        total = len(paths)

        if req.kind == "album_analyze":
            self._run_album(paths=paths, total=total)
            return

        self._run_track(paths=paths, total=total)

    @staticmethod
    def _max_workers(total: int) -> int:
        return min(max(1, os.cpu_count() or 1), max(1, total))

    @staticmethod
    def _cancel_pending_futures(futures: dict[Future[FileResult], Path]) -> None:
        for future in futures:
            if not future.done():
                future.cancel()

    def _run_track(self, *, paths: list[Path], total: int) -> None:
        req = self._request
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
                self._bridge._relay_file_started(path)
                future = executor.submit(
                    analyze_file_task,
                    str(path),
                    target_db=req.target_db,
                    max_amp_only=req.max_amp_only,
                    stored_tag_policy=req.stored_tag_policy,
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
                self._bridge._relay_file_done(result)
                self._bridge._relay_progress(processed, total)

        self._bridge._relay_all_done(
            WorkerResult(
                kind=req.kind,
                total=total,
                succeeded=succeeded,
                failed=failed,
                cancelled=cancelled,
            )
        )

    def _run_album(self, *, paths: list[Path], total: int) -> None:
        req = self._request
        succeeded = 0
        failed = 0
        cancelled = False
        processed = 0

        album_gain_by_path: dict[Path, float | None] = {}
        groups = req.album_groups if req.album_groups else self._group_by_parent(paths)
        group_items = list(groups.values())

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
                    max_amp_only=req.max_amp_only,
                )
                group_futures[future] = tuple(group_paths)

            for future in as_completed(group_futures):
                if self._bridge.is_cancelled and not cancelled:
                    cancelled = True
                    for pending in group_futures:
                        if not pending.done():
                            pending.cancel()
                if future.cancelled():
                    continue
                try:
                    path_texts, album_raw_db = future.result()
                except Exception:
                    continue
                for path_text in path_texts:
                    album_gain_by_path[Path(path_text)] = album_raw_db

        futures: dict[Future[FileResult], Path] = {}
        with ProcessPoolExecutor(max_workers=self._max_workers(total)) as executor:
            for path in paths:
                if cancelled or self._bridge.is_cancelled:
                    cancelled = True
                    break
                self._bridge._relay_file_started(path)
                future = executor.submit(
                    analyze_file_task,
                    str(path),
                    target_db=req.target_db,
                    max_amp_only=req.max_amp_only,
                    stored_tag_policy=req.stored_tag_policy,
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

                album_raw_db = album_gain_by_path.get(path)
                if result.ok and album_raw_db is not None:
                    result = self._with_album_fields(
                        result,
                        target_db=req.target_db,
                        album_raw_db=album_raw_db,
                    )

                if result.ok:
                    succeeded += 1
                else:
                    failed += 1
                processed += 1
                self._bridge._relay_file_done(result)
                self._bridge._relay_progress(processed, total)

        self._bridge._relay_all_done(
            WorkerResult(
                kind=req.kind,
                total=total,
                succeeded=succeeded,
                failed=failed,
                cancelled=cancelled,
            )
        )

    @staticmethod
    def _group_by_parent(paths: list[Path]) -> dict[str, list[Path]]:
        groups: dict[str, list[Path]] = {}
        for path in paths:
            groups.setdefault(str(path.parent), []).append(path)
        return groups

    @staticmethod
    def _with_album_fields(
        result: FileResult, *, target_db: float, album_raw_db: float
    ) -> FileResult:
        album_volume_db = target_db - album_raw_db
        max_amp = result.max_amplitude or 0.0
        clip_album = max_amp * _db_to_linear(album_raw_db) if max_amp else None
        return FileResult(
            path=result.path,
            ok=result.ok,
            error_msg=result.error_msg,
            volume_db=result.volume_db,
            track_gain_db=result.track_gain_db,
            album_gain_db=album_raw_db,
            max_amplitude=result.max_amplitude,
            min_gain_field=result.min_gain_field,
            max_gain_field=result.max_gain_field,
            clipping=result.clipping,
            clip_track=result.clip_track,
            album_volume_db=album_volume_db,
            clip_album=clip_album,
        )


def _db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)
