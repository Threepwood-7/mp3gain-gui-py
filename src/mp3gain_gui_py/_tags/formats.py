"""Tag field name constants and format/parse helpers for MP3Gain tags."""

from __future__ import annotations

# ── Tag key constants ──────────────────────────────────────────────────────────
TAG_TRACK_GAIN = "REPLAYGAIN_TRACK_GAIN"
TAG_TRACK_PEAK = "REPLAYGAIN_TRACK_PEAK"
TAG_ALBUM_GAIN = "REPLAYGAIN_ALBUM_GAIN"
TAG_ALBUM_PEAK = "REPLAYGAIN_ALBUM_PEAK"
TAG_MP3GAIN_UNDO = "MP3GAIN_UNDO"
TAG_MP3GAIN_MINMAX = "MP3GAIN_MINMAX"
TAG_MP3GAIN_ALBUM_MINMAX = "MP3GAIN_ALBUM_MINMAX"

ALL_MP3GAIN_KEYS: frozenset[str] = frozenset({
    TAG_TRACK_GAIN,
    TAG_TRACK_PEAK,
    TAG_ALBUM_GAIN,
    TAG_ALBUM_PEAK,
    TAG_MP3GAIN_UNDO,
    TAG_MP3GAIN_MINMAX,
    TAG_MP3GAIN_ALBUM_MINMAX,
})


# ── Formatters ─────────────────────────────────────────────────────────────────

def format_gain(db: float) -> str:
    """Format a gain value as ``+0.123456 dB`` (9-decimal, explicit sign)."""
    return f"{db:+9.6f} dB"


def format_peak(peak: float) -> str:
    """Format a peak value as a bare 6-decimal float."""
    return f"{peak:<8.6f}"


def format_undo(left: int, right: int, mode: str) -> str:
    """Format an MP3GAIN_UNDO tag value, e.g. ``+006,+006,N``."""
    return f"{left:+04d},{right:+04d},{mode}"


def format_minmax(min_g: int, max_g: int) -> str:
    """Format a MIN/MAX tag value, e.g. ``082,210``."""
    return f"{min_g:03d},{max_g:03d}"


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_gain(raw: str) -> float | None:
    """Parse a gain string like ``+9.210000 dB`` → ``9.21``.

    Returns ``None`` on parse failure.
    """
    try:
        return float(raw.replace("dB", "").strip())
    except ValueError:
        return None


def parse_peak(raw: str) -> float | None:
    """Parse a peak string like ``0.974548`` → ``0.974548``."""
    try:
        return float(raw.strip())
    except ValueError:
        return None


def parse_undo(raw: str) -> tuple[int, int, str] | None:
    """Parse ``+006,+006,N`` → ``(6, 6, 'N')``.

    Returns ``None`` on parse failure.
    """
    parts = raw.strip().split(",")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), parts[2].strip()
    except ValueError:
        return None


def parse_minmax(raw: str) -> tuple[int, int] | None:
    """Parse ``082,210`` → ``(82, 210)``.

    Returns ``None`` on parse failure.
    """
    parts = raw.strip().split(",")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None
