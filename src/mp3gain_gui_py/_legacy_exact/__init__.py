"""Legacy MP3Gain compatibility helpers and processing facade."""

from .math import (
    LEGACY_DB_PER_STEP_APPROX,
    LEGACY_DB_PER_STEP_EXACT,
    db_to_legacy_steps,
    legacy_round_to_int,
    legacy_steps_to_db_approx,
    legacy_steps_to_db_exact,
)
from .processor import LegacyCommandResult, LegacyCompatOptions, LegacyExactProcessor

__all__ = [
    "LEGACY_DB_PER_STEP_APPROX",
    "LEGACY_DB_PER_STEP_EXACT",
    "LegacyCommandResult",
    "LegacyCompatOptions",
    "LegacyExactProcessor",
    "db_to_legacy_steps",
    "legacy_round_to_int",
    "legacy_steps_to_db_approx",
    "legacy_steps_to_db_exact",
]
