"""Legacy MP3Gain gain-step math helpers.

Legacy Pointers:
- LEGACY_PTR:EXACT_DB_STEP_MATH
"""

from __future__ import annotations

import math

# Legacy C exact conversion path: dBchange / (5.0 * log10(2.0))
LEGACY_DB_PER_STEP_EXACT = 5.0 * math.log10(2.0)
# Legacy C approximation used when mutating existing tag values after apply.
LEGACY_DB_PER_STEP_APPROX = 1.505


def legacy_round_to_int(value: float) -> int:
    """Match mp3gain.c integer rounding behavior exactly."""
    abs_value = abs(value)
    truncated = int(abs_value)
    frac = abs_value - float(truncated)
    rounded = truncated if frac < 0.5 else truncated + 1
    return -rounded if value < 0 else rounded


def db_to_legacy_steps(db_gain: float, *, mp3_gain_mod: int = 0) -> int:
    """Convert dB change to legacy MP3 gain steps.

    Legacy pointer: LEGACY_PTR:EXACT_DB_STEP_MATH.
    """
    return legacy_round_to_int(db_gain / LEGACY_DB_PER_STEP_EXACT) + mp3_gain_mod


def legacy_steps_to_db_exact(steps: int) -> float:
    """Convert MP3 gain steps to exact dB using legacy conversion."""
    return steps * LEGACY_DB_PER_STEP_EXACT


def legacy_steps_to_db_approx(steps: int) -> float:
    """Convert MP3 gain steps using legacy tag-update approximation."""
    return steps * LEGACY_DB_PER_STEP_APPROX
