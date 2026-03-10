from __future__ import annotations

from typing import TYPE_CHECKING

from mp3gain_gui_py._legacy_exact.processor import LegacyExactProcessor

if TYPE_CHECKING:
    from pathlib import Path


def test_analyze_track_gain_reports_no_ascii_alias_when_c_backend_scans(
    tmp_path: Path,
) -> None:
    class _BackendStub:
        def scan_track_metrics(
            self,
            _path: Path,
            *,
            include_gain: bool = True,
        ) -> tuple[float, float, int, int]:
            _ = include_gain
            return -7.5, 12345.0, 40, 190

    processor = LegacyExactProcessor.__new__(LegacyExactProcessor)
    processor._backend = _BackendStub()

    src = tmp_path / "Mik L - Ambiancé.mp3"
    src.write_bytes(b"dummy")
    gain_db, used_ascii_alias = processor.analyze_track_gain_db_with_fallback(src)

    assert gain_db == -7.5
    assert used_ascii_alias is False
