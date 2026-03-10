from __future__ import annotations

from typing import Any

from mp3gain_gui_py._settings.domains import OpsSettingsDomain


class _FakeStorage:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def value(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set_value(self, key: str, value: Any) -> None:
        self.values[key] = value


def test_ops_settings_force_apply_defaults_and_roundtrip() -> None:
    storage = _FakeStorage()
    ops = OpsSettingsDomain(storage)  # type: ignore[arg-type]

    assert ops.force_apply_normalization is True
    assert ops.apply_zero_step is False

    ops.force_apply_normalization = False
    ops.apply_zero_step = True

    assert ops.force_apply_normalization is False
    assert ops.apply_zero_step is True
