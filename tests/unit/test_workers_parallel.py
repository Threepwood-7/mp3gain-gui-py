from __future__ import annotations

import math
from concurrent.futures import Future
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import mp3gain_gui_py._workers.analyze_worker as analyze_worker_mod
import mp3gain_gui_py._workers.gain_worker as gain_worker_mod
import mp3gain_gui_py._workers.tag_worker as tag_worker_mod
from mp3gain_gui_py._legacy_exact.math import db_to_legacy_steps
from mp3gain_gui_py._workers.analyze_worker import AnalyzeWorker
from mp3gain_gui_py._workers.gain_worker import GainWorker
from mp3gain_gui_py._workers.tag_worker import TagWorker
from mp3gain_gui_py._workers.types import FileResult, WorkerRequest, WorkerResult

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class _FakeBridge:
    def __init__(self) -> None:
        self.is_cancelled = False
        self.started: list[Path] = []
        self.done: list[FileResult] = []
        self.progress: list[tuple[int, int]] = []
        self.summary: WorkerResult | None = None

    def _relay_file_started(self, path: Path) -> None:
        self.started.append(path)

    def _relay_file_done(self, result: FileResult) -> None:
        self.done.append(result)

    def _relay_progress(self, completed: int, total: int) -> None:
        self.progress.append((completed, total))

    def _relay_all_done(self, result: WorkerResult) -> None:
        self.summary = result


class _FakeProcessPoolExecutor:
    instances: ClassVar[list[_FakeProcessPoolExecutor]] = []

    def __init__(self, *, max_workers: int) -> None:
        self.max_workers = max_workers
        self.submitted: list[tuple[object, tuple[object, ...], dict[str, object]]] = []
        self.__class__.instances.append(self)

    def __enter__(self) -> _FakeProcessPoolExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def submit(
        self,
        fn: object,
        *args: object,
        **kwargs: object,
    ) -> Future[object]:
        self.submitted.append((fn, args, kwargs))
        future: Future[object] = Future()
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            future.set_exception(exc)
        else:
            future.set_result(result)
        return future


def test_gain_worker_uses_process_pool_with_cpu_bound_max_workers(
    monkeypatch: MonkeyPatch,
) -> None:
    paths = [Path(f"file_{i}.mp3") for i in range(8)]
    req = WorkerRequest(kind="undo", paths=paths)
    bridge = _FakeBridge()
    worker = GainWorker(req, bridge)

    _FakeProcessPoolExecutor.instances.clear()
    monkeypatch.setattr(gain_worker_mod.os, "cpu_count", lambda: 4)
    monkeypatch.setattr(
        gain_worker_mod, "ProcessPoolExecutor", _FakeProcessPoolExecutor
    )
    monkeypatch.setattr(
        gain_worker_mod,
        "gain_file_task",
        lambda kind, path_text, **kwargs: FileResult(path=Path(path_text), ok=True),
    )

    worker.run()

    assert bridge.summary is not None
    assert bridge.summary.succeeded == len(paths)
    assert bridge.summary.failed == 0
    assert _FakeProcessPoolExecutor.instances
    assert _FakeProcessPoolExecutor.instances[0].max_workers == 4
    assert len(_FakeProcessPoolExecutor.instances[0].submitted) == len(paths)


def test_analyze_worker_album_merge_maps_group_gain_to_file_results(
    monkeypatch: MonkeyPatch,
) -> None:
    paths = [
        Path(r"C:\tmp\a\one.mp3"),
        Path(r"C:\tmp\a\two.mp3"),
        Path(r"C:\tmp\b\three.mp3"),
    ]
    req = WorkerRequest(
        kind="album_analyze",
        paths=paths,
        album_groups={
            str(paths[0].parent): [paths[0], paths[1]],
            str(paths[2].parent): [paths[2]],
        },
        target_db=89.0,
    )
    bridge = _FakeBridge()
    worker = AnalyzeWorker(req, bridge)

    _FakeProcessPoolExecutor.instances.clear()
    monkeypatch.setattr(analyze_worker_mod.os, "cpu_count", lambda: 4)
    monkeypatch.setattr(
        analyze_worker_mod, "ProcessPoolExecutor", _FakeProcessPoolExecutor
    )

    def _fake_album_group_gain_task(
        path_texts: tuple[str, ...], *, max_amp_only: bool
    ) -> tuple[tuple[str, ...], float | None]:
        _ = max_amp_only
        first = Path(path_texts[0]).parent.name.lower()
        gain = -3.0 if first == "a" else -6.0
        return path_texts, gain

    monkeypatch.setattr(
        analyze_worker_mod, "album_group_gain_task", _fake_album_group_gain_task
    )
    monkeypatch.setattr(
        analyze_worker_mod,
        "analyze_file_task",
        lambda path_text, **kwargs: FileResult(
            path=Path(path_text),
            ok=True,
            volume_db=1.0,
            track_gain_db=-1.0,
            max_amplitude=1000.0,
            min_gain_field=90,
            max_gain_field=150,
        ),
    )

    worker.run()

    assert bridge.summary is not None
    assert bridge.summary.succeeded == len(paths)
    assert bridge.summary.failed == 0

    by_name = {result.path.name: result for result in bridge.done}
    assert by_name["one.mp3"].album_gain_db == -3.0
    assert by_name["two.mp3"].album_gain_db == -3.0
    assert by_name["three.mp3"].album_gain_db == -6.0
    assert by_name["one.mp3"].album_volume_db == 92.0
    assert by_name["three.mp3"].album_volume_db == 95.0
    assert math.isclose(
        by_name["one.mp3"].clip_album or 0.0,
        1000.0 * math.pow(10.0, -3.0 / 20.0),
        rel_tol=1e-9,
    )


def test_tag_worker_uses_process_pool(monkeypatch: MonkeyPatch) -> None:
    paths = [Path(f"tag_{i}.mp3") for i in range(5)]
    req = WorkerRequest(kind="delete_tags", paths=paths)
    bridge = _FakeBridge()
    worker = TagWorker(req, bridge)

    _FakeProcessPoolExecutor.instances.clear()
    monkeypatch.setattr(tag_worker_mod.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(tag_worker_mod, "ProcessPoolExecutor", _FakeProcessPoolExecutor)
    monkeypatch.setattr(
        tag_worker_mod,
        "delete_tags_file_task",
        lambda path_text, *, tag_mode="apev2": FileResult(
            path=Path(path_text), ok=True
        ),
    )

    worker.run()

    assert bridge.summary is not None
    assert bridge.summary.succeeded == len(paths)
    assert bridge.summary.failed == 0
    assert _FakeProcessPoolExecutor.instances
    assert _FakeProcessPoolExecutor.instances[0].max_workers == len(paths)
    for _fn, _args, kwargs in _FakeProcessPoolExecutor.instances[0].submitted:
        assert kwargs.get("tag_mode") == "apev2"


def test_gain_worker_forced_album_normalization_precomputes_group_steps(
    monkeypatch: MonkeyPatch,
) -> None:
    paths = [
        Path(r"C:\tmp\a\one.mp3"),
        Path(r"C:\tmp\a\two.mp3"),
        Path(r"C:\tmp\b\three.mp3"),
    ]
    req = WorkerRequest(
        kind="apply_album",
        paths=paths,
        album_groups={
            str(paths[0].parent): [paths[0], paths[1]],
            str(paths[2].parent): [paths[2]],
        },
        target_db=87.0,
        force_apply_normalization=True,
    )
    bridge = _FakeBridge()
    worker = GainWorker(req, bridge)

    _FakeProcessPoolExecutor.instances.clear()
    monkeypatch.setattr(gain_worker_mod.os, "cpu_count", lambda: 4)
    monkeypatch.setattr(
        gain_worker_mod, "ProcessPoolExecutor", _FakeProcessPoolExecutor
    )

    def _fake_album_group_gain_task(
        path_texts: tuple[str, ...], *, max_amp_only: bool
    ) -> tuple[tuple[str, ...], float | None]:
        _ = max_amp_only
        first = Path(path_texts[0]).parent.name.lower()
        gain = 3.010299956639812 if first == "a" else -3.010299956639812
        return path_texts, gain

    monkeypatch.setattr(
        gain_worker_mod, "album_group_gain_task", _fake_album_group_gain_task
    )
    monkeypatch.setattr(
        gain_worker_mod,
        "gain_file_task",
        lambda kind, path_text, **kwargs: FileResult(path=Path(path_text), ok=True),
    )

    worker.run()

    assert bridge.summary is not None
    assert bridge.summary.succeeded == len(paths)
    assert bridge.summary.failed == 0
    assert len(_FakeProcessPoolExecutor.instances) == 2

    apply_executor = _FakeProcessPoolExecutor.instances[1]
    submitted_by_path = {
        Path(args[1]): kwargs for _fn, args, kwargs in apply_executor.submitted
    }
    expected_a = db_to_legacy_steps(3.010299956639812) + db_to_legacy_steps(87.0 - 89.0)
    expected_b = db_to_legacy_steps(-3.010299956639812) + db_to_legacy_steps(
        87.0 - 89.0
    )
    assert submitted_by_path[paths[0]]["forced_steps"] == expected_a
    assert submitted_by_path[paths[1]]["forced_steps"] == expected_a
    assert submitted_by_path[paths[2]]["forced_steps"] == expected_b
    assert submitted_by_path[paths[0]]["force_apply_normalization"] is True
