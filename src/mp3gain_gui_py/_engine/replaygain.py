"""GainAnalyzer - faithful Python port of gain_analysis.c.

Legacy Pointers:
- LEGACY_PTR:DSP_ANALYZE_SAMPLES
- LEGACY_PTR:DSP_GET_TITLE_GAIN

Original algorithm: David Robinson / Glen Sawyer - LGPL 2.1.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from .coefficients import (
    AB_BUTTER,
    AB_YULE,
    FREQ_TO_INDEX,
    GAIN_NOT_ENOUGH_SAMPLES,
    MAX_DB,
    MAX_ORDER,
    PINK_REF,
    RMS_PERCENTILE,
    RMS_WINDOW_TIME_MS,
    STEPS_PER_DB,
)

# ── Select filter backend at import time ───────────────────────────────────────
_FilterFn = Callable[[list[float], list[float], int, tuple[float, ...]], list[float]]

try:
    from . import filter_np as _filter_mod  # type: ignore[import-not-found]

    _NUMPY = True
except ImportError:
    from . import filter_py as _filter_mod  # type: ignore[assignment]

    _NUMPY = False

_filter_yule: _FilterFn = _filter_mod.filter_yule
_filter_butter: _FilterFn = _filter_mod.filter_butter

USING_NUMPY: bool = _NUMPY


# ── Public API ─────────────────────────────────────────────────────────────────


class GainAnalyzer:
    """Stateful ReplayGain loudness analyser.

    Usage (matching the C pseudo-code)::

        ga = GainAnalyzer(44100)
        for left, right in decode_chunks(song):
            ga.analyze_samples(left, right, len(left))
        track_gain = ga.get_title_gain()  # resets per-track state
        album_gain = ga.get_album_gain()  # accumulated across all tracks
    """

    def __init__(self, sample_rate: int) -> None:
        if sample_rate not in FREQ_TO_INDEX:
            raise ValueError(
                f"Unsupported sample rate {sample_rate}. "
                f"Supported: {sorted(FREQ_TO_INDEX)}"
            )
        self._freq_idx = FREQ_TO_INDEX[sample_rate]
        self._sample_window: int = math.ceil(sample_rate * RMS_WINDOW_TIME_MS / 1000.0)

        # IIR pre-buffers (last MAX_ORDER samples of each signal stage, per channel)
        self._l_in_pre: list[float] = [0.0] * MAX_ORDER
        self._r_in_pre: list[float] = [0.0] * MAX_ORDER
        self._l_step_pre: list[float] = [0.0] * MAX_ORDER  # yule output history
        self._r_step_pre: list[float] = [0.0] * MAX_ORDER
        self._l_out_pre: list[float] = [0.0] * MAX_ORDER  # butter output history
        self._r_out_pre: list[float] = [0.0] * MAX_ORDER

        # RMS window accumulators
        self._lsum: float = 0.0
        self._rsum: float = 0.0
        self._totsamp: int = 0

        # Histograms: A = current track, B = album accumulator
        _hist_len = STEPS_PER_DB * MAX_DB
        self._hist_a: list[int] = [0] * _hist_len
        self._hist_b: list[int] = [0] * _hist_len

    # ── Analysis ───────────────────────────────────────────────────────────────

    def analyze_samples(
        self,
        left: list[float],
        right: list[float] | None,
        num_samples: int,
    ) -> None:
        """Feed PCM samples into the analyser.

        Legacy pointer: LEGACY_PTR:DSP_ANALYZE_SAMPLES.

        Args:
            left:        Left-channel samples (or mono channel).
            right:       Right-channel samples.  Pass ``None`` for mono —
                         the left channel will be used for both channels.
            num_samples: Number of samples to consume from ``left``/``right``.
        """
        if num_samples == 0:
            return

        right_buf: list[float] = left if right is None else right

        yule_k = AB_YULE[self._freq_idx]
        butter_k = AB_BUTTER[self._freq_idx]

        pos = 0
        remaining = num_samples

        while remaining > 0:
            batch = min(remaining, self._sample_window - self._totsamp)

            # Build extended input (pre-buffer + current batch)
            l_in_ext = self._l_in_pre + left[pos : pos + batch]
            r_in_ext = self._r_in_pre + right_buf[pos : pos + batch]

            # Yule filter
            l_step = _filter_yule(l_in_ext, self._l_step_pre, batch, yule_k)
            r_step = _filter_yule(r_in_ext, self._r_step_pre, batch, yule_k)

            # Butterworth filter (input = yule output, with its pre-buffer)
            l_step_ext = self._l_step_pre + l_step
            r_step_ext = self._r_step_pre + r_step
            l_out = _filter_butter(l_step_ext, self._l_out_pre, batch, butter_k)
            r_out = _filter_butter(r_step_ext, self._r_out_pre, batch, butter_k)

            # Update pre-buffers
            self._l_in_pre = (self._l_in_pre + left[pos : pos + batch])[-MAX_ORDER:]
            self._r_in_pre = (self._r_in_pre + right_buf[pos : pos + batch])[
                -MAX_ORDER:
            ]
            self._l_step_pre = (self._l_step_pre + l_step)[-MAX_ORDER:]
            self._r_step_pre = (self._r_step_pre + r_step)[-MAX_ORDER:]
            self._l_out_pre = (self._l_out_pre + l_out)[-MAX_ORDER:]
            self._r_out_pre = (self._r_out_pre + r_out)[-MAX_ORDER:]

            # Accumulate squared RMS sum
            self._lsum += sum(v * v for v in l_out)
            self._rsum += sum(v * v for v in r_out)

            self._totsamp += batch
            pos += batch
            remaining -= batch

            if self._totsamp == self._sample_window:
                val = (
                    STEPS_PER_DB
                    * 10.0
                    * math.log10(
                        (self._lsum + self._rsum) / self._totsamp * 0.5 + 1.0e-37
                    )
                )
                ival = max(0, min(int(val), STEPS_PER_DB * MAX_DB - 1))
                self._hist_a[ival] += 1
                self._lsum = self._rsum = 0.0
                self._totsamp = 0

    # ── Results ────────────────────────────────────────────────────────────────

    def get_title_gain(self) -> float:
        """Return recommended dB gain for all samples since last call.

        Legacy pointer: LEGACY_PTR:DSP_GET_TITLE_GAIN.

        Merges track histogram into album histogram, then resets all
        per-track state (mirrors GetTitleGain in the C source).
        """
        result = _analyze_result(self._hist_a)

        # Merge A → B, then clear A
        for i in range(len(self._hist_a)):
            self._hist_b[i] += self._hist_a[i]
            self._hist_a[i] = 0

        # Reset per-track filter state (C code: zeros linprebuf etc.)
        self._l_in_pre = [0.0] * MAX_ORDER
        self._r_in_pre = [0.0] * MAX_ORDER
        self._l_step_pre = [0.0] * MAX_ORDER
        self._r_step_pre = [0.0] * MAX_ORDER
        self._l_out_pre = [0.0] * MAX_ORDER
        self._r_out_pre = [0.0] * MAX_ORDER
        self._totsamp = 0
        self._lsum = self._rsum = 0.0

        return result

    def get_album_gain(self) -> float:
        """Return recommended dB gain for all tracks analyzed so far."""
        return _analyze_result(self._hist_b)


# ── Internal helper ────────────────────────────────────────────────────────────


def _analyze_result(histogram: list[int]) -> float:
    """Compute ReplayGain value from a histogram of RMS levels.

    Finds the 95th-percentile loudness bucket (counts down from the top
    until 5 % of samples are above the threshold) and converts it to dB.
    """
    total = sum(histogram)
    if total == 0:
        return GAIN_NOT_ENOUGH_SAMPLES

    upper = math.ceil(total * (1.0 - RMS_PERCENTILE))  # top 5 % count
    i = len(histogram) - 1
    while i >= 0:
        upper -= histogram[i]
        if upper <= 0:
            break
        i -= 1

    return PINK_REF - i / STEPS_PER_DB
