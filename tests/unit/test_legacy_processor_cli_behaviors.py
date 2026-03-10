from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mp3gain_gui_py._legacy_exact.processor import (
    LegacyCompatOptions,
    LegacyExactProcessor,
)
from mp3gain_gui_py._mp3.frame_parser import FrameHeader

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _disable_c_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP3GAIN_GUI_PY_DISABLE_C_BACKEND", "1")


def _frame_header(*, channel_mode: int, num_channels: int) -> FrameHeader:
    return FrameHeader(
        sync_valid=True,
        mpeg_version=0x03,
        layer=0x01,
        crc_protected=False,
        bitrate_kbps=128,
        sample_rate_hz=44100,
        padding=False,
        channel_mode=channel_mode,
        num_channels=num_channels,
        frame_size_bytes=417,
    )


def test_compute_autoclip_steps_uses_legacy_integer_bounds() -> None:
    processor = LegacyExactProcessor()
    assert processor.compute_autoclip_steps(12, min_gain=2, max_gain=250) == 5
    assert processor.compute_autoclip_steps(-12, min_gain=3, max_gain=200) == -3
    assert processor.compute_autoclip_steps(4, min_gain=0, max_gain=100) == 4


def test_single_channel_rejects_mono(tmp_path: Path) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"dummy")
    processor = LegacyExactProcessor()
    options = LegacyCompatOptions()

    processor._read_first_audio_header = lambda _path: _frame_header(channel_mode=0x03, num_channels=1)  # type: ignore[method-assign]
    result = processor.apply_single_channel_steps(
        target,
        channel_index=0,
        steps=3,
        options=options,
    )
    assert result.exit_code == 1
    assert "mono" in result.message.lower()


def test_single_channel_rejects_joint_stereo(tmp_path: Path) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"dummy")
    processor = LegacyExactProcessor()
    options = LegacyCompatOptions()

    processor._read_first_audio_header = lambda _path: _frame_header(channel_mode=0x01, num_channels=2)  # type: ignore[method-assign]
    result = processor.apply_single_channel_steps(
        target,
        channel_index=1,
        steps=3,
        options=options,
    )
    assert result.exit_code == 1
    assert "joint stereo" in result.message.lower()


def test_single_channel_applies_right_channel_only(monkeypatch: object, tmp_path: Path) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"dummy")
    processor = LegacyExactProcessor()
    options = LegacyCompatOptions()
    captured: dict[str, int | bool] = {}

    processor._read_first_audio_header = lambda _path: _frame_header(channel_mode=0x00, num_channels=2)  # type: ignore[method-assign]

    def fake_apply_gain_change(
        path: Path,
        gain_delta: int,
        *,
        wrap: bool = False,
        preserve_timestamp: bool = False,
        use_temp_file: bool = True,
        gain_delta_right: int | None = None,
    ) -> None:
        _ = path
        captured["gain_delta"] = gain_delta
        captured["gain_delta_right"] = gain_delta_right if gain_delta_right is not None else 0
        captured["wrap"] = wrap
        captured["preserve_timestamp"] = preserve_timestamp
        captured["use_temp_file"] = use_temp_file

    monkeypatch.setattr("mp3gain_gui_py._legacy_exact.processor.apply_gain_change", fake_apply_gain_change)

    result = processor.apply_single_channel_steps(
        target,
        channel_index=1,
        steps=4,
        options=options,
    )
    assert result.exit_code == 0
    assert captured["gain_delta"] == 0
    assert captured["gain_delta_right"] == 4
