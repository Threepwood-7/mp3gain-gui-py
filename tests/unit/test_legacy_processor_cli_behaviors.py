from __future__ import annotations

from typing import TYPE_CHECKING

from mp3gain_gui_py._legacy_exact.processor import (
    LegacyCompatOptions,
    LegacyExactProcessor,
)
from mp3gain_gui_py._tags.reader import TagData

if TYPE_CHECKING:
    from pathlib import Path


def test_compute_autoclip_steps_uses_legacy_integer_bounds() -> None:
    class _BackendStub:
        def scan_track_metrics(
            self,
            _path: Path,
            *,
            include_gain: bool = True,
        ) -> tuple[float, float, int, int]:
            _ = include_gain
            return -9.0, 32768.0, 2, 250

    processor = LegacyExactProcessor.__new__(LegacyExactProcessor)
    processor._backend = _BackendStub()
    assert processor.compute_autoclip_steps(12, min_gain=2, max_gain=250) == 5
    assert processor.compute_autoclip_steps(-12, min_gain=3, max_gain=200) == -3
    assert processor.compute_autoclip_steps(4, min_gain=0, max_gain=100) == 4


def test_single_channel_rejects_invalid_channel(tmp_path: Path) -> None:
    class _BackendStub:
        def apply_gain_file(self, *args: object, **kwargs: object) -> None:
            _ = (args, kwargs)

    target = tmp_path / "sample.mp3"
    target.write_bytes(b"dummy")
    processor = LegacyExactProcessor.__new__(LegacyExactProcessor)
    processor._backend = _BackendStub()

    result = processor.apply_single_channel_steps(
        target,
        channel_index=2,
        steps=3,
        options=LegacyCompatOptions(),
    )
    assert result.exit_code == 1
    assert "channel index" in result.message.lower()


def test_single_channel_applies_right_channel_only(tmp_path: Path) -> None:
    captured: dict[str, int | bool] = {}

    class _BackendStub:
        def apply_gain_file(
            self,
            _path: Path,
            *,
            left_gain_steps: int,
            right_gain_steps: int,
            wrap_gain: bool,
            preserve_timestamp: bool,
            use_temp_file: bool,
        ) -> None:
            captured["left_gain_steps"] = left_gain_steps
            captured["right_gain_steps"] = right_gain_steps
            captured["wrap_gain"] = wrap_gain
            captured["preserve_timestamp"] = preserve_timestamp
            captured["use_temp_file"] = use_temp_file

        def read_tags(self, _path: Path) -> TagData:
            return TagData(tag_format="none")

    target = tmp_path / "sample.mp3"
    target.write_bytes(b"dummy")
    processor = LegacyExactProcessor.__new__(LegacyExactProcessor)
    processor._backend = _BackendStub()

    result = processor.apply_single_channel_steps(
        target,
        channel_index=1,
        steps=4,
        options=LegacyCompatOptions(),
    )
    assert result.exit_code == 0
    assert captured["left_gain_steps"] == 0
    assert captured["right_gain_steps"] == 4
