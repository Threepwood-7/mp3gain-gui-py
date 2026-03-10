"""Legacy C backend facade."""

from .runtime import (
    CBackendError,
    CBackendPathError,
    CBackendUnavailable,
    CBackendUnavailableError,
    LegacyCBackend,
    get_backend,
)

__all__ = [
    "CBackendError",
    "CBackendPathError",
    "CBackendUnavailable",
    "CBackendUnavailableError",
    "LegacyCBackend",
    "get_backend",
]
