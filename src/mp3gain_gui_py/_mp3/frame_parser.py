"""MPEG Layer III frame header parsing and global_gain field location.

Bit-level logic mirrors scanFrameGain() / changeGain() from mp3gain.c.
"""

from __future__ import annotations

from dataclasses import dataclass

# MPEG version bits (header byte 1, bits 4-3)
_MPEG1 = 0x03

# Channel mode values (header byte 3, bits 7-6)
_MONO = 0x03

# Bitrate table [mpeg_ver_idx][bitrate_idx] in kbps
_BITRATE: tuple[tuple[int, ...], ...] = (
    # MPEG 2.5  (ver 0x00)
    (0,  8, 16, 24, 32, 40, 48, 56,  64,  80,  96, 112, 128, 144, 160, 0),
    # reserved  (ver 0x01)
    (0,  0,  0,  0,  0,  0,  0,  0,   0,   0,   0,   0,   0,   0,   0, 0),
    # MPEG 2    (ver 0x02)
    (0,  8, 16, 24, 32, 40, 48, 56,  64,  80,  96, 112, 128, 144, 160, 0),
    # MPEG 1    (ver 0x03)
    (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0),
)

# Sample-rate table [mpeg_ver_idx][freq_idx] in Hz
_SAMPLERATE: tuple[tuple[int, ...], ...] = (
    # MPEG 2.5
    (11025, 12000,  8000, 0),
    # reserved
    (    0,     0,     0, 0),
    # MPEG 2
    (22050, 24000, 16000, 0),
    # MPEG 1
    (44100, 48000, 32000, 0),
)


@dataclass(slots=True)
class FrameHeader:
    """Decoded MPEG Layer III frame header."""

    sync_valid: bool
    mpeg_version: int       # raw bits (0x03=MPEG1, 0x02=MPEG2, 0x00=MPEG2.5)
    layer: int              # raw bits (0x01=LayerIII)
    crc_protected: bool     # True when CRC field is present (protection_bit == 0)
    bitrate_kbps: int
    sample_rate_hz: int
    padding: bool
    channel_mode: int       # raw bits (0x03=mono, else stereo variants)
    num_channels: int       # 1 or 2
    frame_size_bytes: int   # total frame size in bytes (header + data)


def parse_frame_header(data: bytes, offset: int) -> FrameHeader | None:
    """Parse a 4-byte MPEG frame header at ``data[offset]``.

    Returns ``None`` if the header is not a valid MPEG Layer III frame.
    """
    if offset + 4 > len(data):
        return None

    b0 = data[offset]
    b1 = data[offset + 1]
    b2 = data[offset + 2]
    b3 = data[offset + 3]

    # Sync word: all 11 bits must be 1
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return None

    mpeg_ver = (b1 >> 3) & 0x03
    layer = (b1 >> 1) & 0x03

    # Layer III = 0x01 in the 2-bit field
    if layer != 0x01:
        return None

    # Invalid MPEG version reserved slot
    if mpeg_ver == 0x01:
        return None

    bitrate_idx = (b2 >> 4) & 0x0F
    freq_idx = (b2 >> 2) & 0x03

    if bitrate_idx == 0x0F or bitrate_idx == 0x00:
        return None   # forbidden / free-format
    if freq_idx == 0x03:
        return None   # reserved

    crc_protected = not bool(b1 & 0x01)  # protection_bit=0 means CRC present
    bitrate_kbps = _BITRATE[mpeg_ver][bitrate_idx]
    sample_rate_hz = _SAMPLERATE[mpeg_ver][freq_idx]

    if bitrate_kbps == 0 or sample_rate_hz == 0:
        return None

    padding = bool((b2 >> 1) & 0x01)
    channel_mode = (b3 >> 6) & 0x03
    num_channels = 1 if channel_mode == _MONO else 2

    # Frame size = floor(144 * bitrate / samplerate) + padding  (MPEG1 Layer III)
    # MPEG2/2.5 uses 72 * bitrate / samplerate
    bitbase = 144.0 if mpeg_ver == _MPEG1 else 72.0

    frame_size = int(bitbase * bitrate_kbps * 1000 / sample_rate_hz) + (1 if padding else 0)

    return FrameHeader(
        sync_valid=True,
        mpeg_version=mpeg_ver,
        layer=layer,
        crc_protected=crc_protected,
        bitrate_kbps=bitrate_kbps,
        sample_rate_hz=sample_rate_hz,
        padding=padding,
        channel_mode=channel_mode,
        num_channels=num_channels,
        frame_size_bytes=frame_size,
    )


def find_next_frame(data: bytes, start: int) -> int:
    """Return offset of the next valid MPEG Layer III sync word at or after ``start``.

    Returns ``-1`` if none found.
    """
    i = start
    limit = len(data) - 3
    while i <= limit:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0 and parse_frame_header(data, i) is not None:
            return i
        i += 1
    return -1


def global_gain_offsets(header: FrameHeader) -> list[tuple[int, int]]:
    """Return ``[(byte_offset, bit_offset), ...]`` for each global_gain field.

    Offsets are relative to the start of the frame (i.e. include the 4-byte
    header and optional 2-byte CRC).

    Mirrors the bit-walking in scanFrameGain() / changeGain() from mp3gain.c.

    Bit layout (bit 0 = MSB of first sideinfo byte):

    MPEG1 stereo (32-byte sideinfo):
      bit 0-8   main_data_begin (9)
      bit 9-11  private_bits (3)
      bit 12-19 scfsi 2x4
      granulexchannelx58-bit blocks, global_gain at offset+21 within each

    MPEG1 mono (17-byte sideinfo):
      bit 0-8   main_data_begin (9)
      bit 9-13  private_bits (5)
      bit 14-17 scfsi 1x4
      granulexchannelx58-bit blocks

    MPEG2 stereo (17-byte sideinfo):
      bit 0-7   main_data_begin (8)
      bit 8-9   private_bits (2)
      channelx63-bit blocks, global_gain at offset+21 within each

    MPEG2 mono (9-byte sideinfo):
      bit 0-7   main_data_begin (8)
      bit 8     private_bits (1)
      channelx63-bit block
    """
    is_mpeg1 = (header.mpeg_version == _MPEG1)
    nchan = header.num_channels
    mono = (nchan == 1)

    # Number of bits from start of sideinfo to first channel-block
    if is_mpeg1:
        pre_bits = 9 + (5 if mono else 3) + (nchan * 4)  # main_data_begin + private + scfsi
        n_granules = 2
        block_bits = 59  # 21 skip + 8 gain + 30 remainder (21+38 total advance = 59)
    else:
        pre_bits = 8 + (1 if mono else 2)
        n_granules = 1
        block_bits = 63  # 21 skip + 8 gain + 34 remainder (21+42 total advance = 63)

    # Byte offset of sideinfo start from frame start
    sideinfo_byte = 4 + (2 if header.crc_protected else 0)

    results: list[tuple[int, int]] = []
    for _gr in range(n_granules):
        for _ch in range(nchan):
            # global_gain is at pre_bits + 21 bits into current block
            bit_pos = pre_bits + 21
            abs_bit = sideinfo_byte * 8 + bit_pos
            results.append((abs_bit // 8, abs_bit % 8))
            pre_bits += block_bits

    return results


def has_xing_or_info_tag(data: bytes, frame_offset: int, header: FrameHeader) -> bool:
    """Return True if *header* frame carries a Xing/Info VBR header marker."""
    if header.mpeg_version == _MPEG1:
        sideinfo_len = 17 if header.num_channels == 1 else 32
    else:
        sideinfo_len = 9 if header.num_channels == 1 else 17

    sideinfo_start = frame_offset + 4 + (2 if header.crc_protected else 0)
    marker_offset = sideinfo_start + sideinfo_len
    marker = data[marker_offset: marker_offset + 4]
    return marker in (b"Xing", b"Info")
