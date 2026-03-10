from __future__ import annotations

from pathlib import Path

from mp3gain_gui_py._workers.types import WorkerRequest


def test_worker_request_has_max_amp_only_default_false() -> None:
    req = WorkerRequest(kind="track_analyze", paths=[Path("sample.mp3")])
    assert req.max_amp_only is False
