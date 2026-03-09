"""CRC-16 calculation for protected MPEG frames.

Legacy Pointers:
- LEGACY_PTR:MP3_CRC_UPDATE
- LEGACY_PTR:MP3_CRC_WRITE_HEADER

Mirrors crcUpdate() / crcWriteHeader() from mp3gain.c.
Polynomial: 0x8005.
"""

from __future__ import annotations

_POLYNOMIAL = 0x8005


def crc16_update(value: int, crc: int) -> int:
    """Feed one byte ``value`` into a running CRC-16 computation.

    Legacy pointer: LEGACY_PTR:MP3_CRC_UPDATE.
    """
    value <<= 8
    for _ in range(8):
        value <<= 1
        crc <<= 1
        if (crc ^ value) & 0x10000:
            crc ^= _POLYNOMIAL
    return crc & 0xFFFF


def compute_frame_crc(frame: bytes | bytearray) -> int:
    """Compute the CRC-16 over the protected parts of a frame.

    The C code protects header bytes [2] and [3], then all sideinfo bytes
    starting at byte [6] (bytes [4..5] hold the stored CRC itself).

    Args:
        frame: Full raw frame bytes (must include header + CRC field).

    Returns:
        16-bit CRC value.
    """
    crc = 0xFFFF
    crc = crc16_update(frame[2], crc)
    crc = crc16_update(frame[3], crc)
    # sideinfo starts at byte 6
    for i in range(6, len(frame)):
        crc = crc16_update(frame[i], crc)
        # stop when we've covered the sideinfo region
        # (callers pass only header+sideinfo, not the full frame)
    return crc & 0xFFFF


def write_frame_crc(frame: bytearray, sideinfo_end: int) -> None:
    """Recalculate and write CRC into ``frame[4:6]``.

    Legacy pointer: LEGACY_PTR:MP3_CRC_WRITE_HEADER.

    Args:
        frame:        Mutable frame buffer (modified in-place).
        sideinfo_end: Byte index (exclusive) of the end of sideinfo within
                      ``frame`` — only bytes [6..sideinfo_end) are covered.
    """
    crc = 0xFFFF
    crc = crc16_update(frame[2], crc)
    crc = crc16_update(frame[3], crc)
    for i in range(6, sideinfo_end):
        crc = crc16_update(frame[i], crc)
    frame[4] = (crc >> 8) & 0xFF
    frame[5] = crc & 0xFF
