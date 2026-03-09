from __future__ import annotations

from typing import TYPE_CHECKING

from mp3gain_gui_py._legacy_exact.processor import LegacyExactProcessor

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def test_analyze_track_gain_db_falls_back_to_ascii_alias(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    processor = LegacyExactProcessor()
    src = tmp_path / "Mik L - Ambianc\u00e9.mp3"
    src.write_bytes(b"dummy")

    class DummyGainAnalyzer:
        def __init__(self, sample_rate: int) -> None:
            self.sample_rate = sample_rate

        def analyze_samples(self, left: list[float], right: list[float], num_samples: int) -> None:
            _ = (left, right, num_samples, self.sample_rate)

        def get_title_gain(self) -> float:
            return -7.5

    def fake_read_mp3_info(path: Path | str) -> tuple[int, int]:
        text = str(path)
        if any(ord(ch) > 127 for ch in text):
            raise ValueError("decode failed")
        return 44100, 2

    def fake_decode_to_stereo_chunks(
        path: Path | str,
        chunk_frames: int = 4096,
    ) -> Iterator[tuple[int, list[float], list[float]]]:
        _ = (path, chunk_frames)
        yield (44100, [1.0], [1.0])

    monkeypatch.setattr("mp3gain_gui_py._legacy_exact.processor.GainAnalyzer", DummyGainAnalyzer)
    monkeypatch.setattr("mp3gain_gui_py._legacy_exact.processor.read_mp3_info", fake_read_mp3_info)
    monkeypatch.setattr(
        "mp3gain_gui_py._legacy_exact.processor.decode_to_stereo_chunks",
        fake_decode_to_stereo_chunks,
    )

    gain_db, used_ascii_alias = processor.analyze_track_gain_db_with_fallback(src)
    assert gain_db == -7.5
    assert used_ascii_alias is True
