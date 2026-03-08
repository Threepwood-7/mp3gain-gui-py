"""Value coercion helpers for settings storage."""

from __future__ import annotations

from typing import Any


def normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    if isinstance(value, int):
        return bool(value)
    return default


def normalize_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def normalize_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def normalize_int_list(value: Any, default: list[int] | None = None) -> list[int]:
    if default is None:
        default = []
    if isinstance(value, list):
        try:
            return [int(x) for x in value]  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
    return default


def normalize_bytes(value: Any, default: bytes = b"") -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return default
