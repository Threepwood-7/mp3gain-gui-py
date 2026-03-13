"""NumPy-accelerated Yule + Butterworth IIR filters.

Legacy Pointers:
- LEGACY_PTR:DSP_FILTER_YULE
- LEGACY_PTR:DSP_FILTER_BUTTER

Same signatures as filter_py; uses numpy arrays internally for faster
floating-point arithmetic.  Falls back gracefully — callers should import
from replaygain.py which selects the implementation at module load time.
"""

from __future__ import annotations

import importlib
from typing import Protocol, cast, overload

from .coefficients import MAX_ORDER


class _NDArrayLike(Protocol):
    @overload
    def __getitem__(self, key: int) -> float: ...

    @overload
    def __getitem__(self, key: slice) -> _NDArrayLike: ...

    @overload
    def __getitem__(self, key: object) -> float | _NDArrayLike: ...

    @overload
    def __setitem__(
        self,
        key: int,
        value: float,
    ) -> None: ...

    @overload
    def __setitem__(
        self,
        key: slice,
        value: list[float] | _NDArrayLike,
    ) -> None: ...

    @overload
    def __setitem__(
        self,
        key: object,
        value: object,
    ) -> None: ...

    def tolist(self) -> list[float]: ...


class _NumpyModuleLike(Protocol):
    float64: object

    def asarray(self, _obj: object, **_kwargs: object) -> _NDArrayLike: ...

    def empty(self, _shape: int, **_kwargs: object) -> _NDArrayLike: ...


# NumPy is an optional fast-path dependency, so import it lazily and type it
# against the narrow surface this module actually uses.
np = cast("_NumpyModuleLike", importlib.import_module("numpy"))


def filter_yule(
    input_buf: list[float],
    output_pre: list[float],
    n_samples: int,
    kernel: tuple[float, ...],
) -> list[float]:
    """NumPy-accelerated 10th-order Yule IIR filter (same contract as filter_py).

    Legacy pointer: LEGACY_PTR:DSP_FILTER_YULE.
    """
    k = np.asarray(kernel, dtype=np.float64)
    inp = np.empty(MAX_ORDER + n_samples, dtype=np.float64)
    inp[:MAX_ORDER] = input_buf[:MAX_ORDER]
    inp[MAX_ORDER:] = input_buf[MAX_ORDER : MAX_ORDER + n_samples]

    out = np.empty(MAX_ORDER + n_samples, dtype=np.float64)
    out[:MAX_ORDER] = output_pre

    for i in range(n_samples):
        j = MAX_ORDER + i
        out[j] = (
            1e-10
            + inp[j] * k[0]
            - out[j - 1] * k[1]
            + inp[j - 1] * k[2]
            - out[j - 2] * k[3]
            + inp[j - 2] * k[4]
            - out[j - 3] * k[5]
            + inp[j - 3] * k[6]
            - out[j - 4] * k[7]
            + inp[j - 4] * k[8]
            - out[j - 5] * k[9]
            + inp[j - 5] * k[10]
            - out[j - 6] * k[11]
            + inp[j - 6] * k[12]
            - out[j - 7] * k[13]
            + inp[j - 7] * k[14]
            - out[j - 8] * k[15]
            + inp[j - 8] * k[16]
            - out[j - 9] * k[17]
            + inp[j - 9] * k[18]
            - out[j - 10] * k[19]
            + inp[j - 10] * k[20]
        )

    return out[MAX_ORDER:].tolist()


def filter_butter(
    input_buf: list[float],
    output_pre: list[float],
    n_samples: int,
    kernel: tuple[float, ...],
) -> list[float]:
    """NumPy-accelerated 2nd-order Butterworth IIR filter.

    Legacy pointer: LEGACY_PTR:DSP_FILTER_BUTTER.
    """
    k = np.asarray(kernel, dtype=np.float64)
    inp = np.empty(MAX_ORDER + n_samples, dtype=np.float64)
    inp[:MAX_ORDER] = input_buf[:MAX_ORDER]
    inp[MAX_ORDER:] = input_buf[MAX_ORDER : MAX_ORDER + n_samples]

    out = np.empty(MAX_ORDER + n_samples, dtype=np.float64)
    out[:MAX_ORDER] = output_pre

    for i in range(n_samples):
        j = MAX_ORDER + i
        out[j] = (
            inp[j] * k[0]
            - out[j - 1] * k[1]
            + inp[j - 1] * k[2]
            - out[j - 2] * k[3]
            + inp[j - 2] * k[4]
        )

    return out[MAX_ORDER:].tolist()
