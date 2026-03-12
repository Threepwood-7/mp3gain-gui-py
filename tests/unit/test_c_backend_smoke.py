from __future__ import annotations

from pathlib import Path

import pytest

from mp3gain_gui_py._c_backend import CBackendError, CBackendUnavailable, get_backend


def test_c_backend_build_and_error_path() -> None:
    try:
        backend = get_backend(auto_build=True)
    except CBackendUnavailable as exc:
        pytest.skip(f"C backend unavailable: {exc}")
        return

    missing = Path("c:/tmp/pycompa/definitely_missing_mp3gain_input.mp3")
    with pytest.raises(CBackendError):
        backend.apply_gain_file(
            missing,
            left_gain_steps=1,
            right_gain_steps=1,
            wrap_gain=False,
            preserve_timestamp=False,
            use_temp_file=True,
        )
