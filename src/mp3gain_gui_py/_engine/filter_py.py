"""Pure-Python Yule + Butterworth IIR filters.

Faithful translation of filterYule / filterButter from gain_analysis.c.
The caller is responsible for maintaining pre-buffers (last MAX_ORDER samples
of both input and output) across calls.
"""

from __future__ import annotations

from .coefficients import MAX_ORDER


def filter_yule(
    input_buf: list[float],
    output_pre: list[float],
    n_samples: int,
    kernel: tuple[float, ...],
) -> list[float]:
    """Apply 10th-order Yule IIR filter.

    Args:
        input_buf:  Pre-buffer (MAX_ORDER values) followed by n_samples current
                    samples.  Length must be >= MAX_ORDER + n_samples.
        output_pre: Previous MAX_ORDER output values (pre-buffer only).
                    Length must be exactly MAX_ORDER.
        n_samples:  Number of new samples to process.
        kernel:     21-element coefficient tuple (b0,a1,b1,a2,...,a10,b10).

    Returns:
        List of n_samples output values.
    """
    out: list[float] = list(output_pre)
    for i in range(n_samples):
        j = MAX_ORDER + i
        val = (
            1e-10
            + input_buf[j]      * kernel[0]
            - out[j - 1]        * kernel[1]
            + input_buf[j - 1]  * kernel[2]
            - out[j - 2]        * kernel[3]
            + input_buf[j - 2]  * kernel[4]
            - out[j - 3]        * kernel[5]
            + input_buf[j - 3]  * kernel[6]
            - out[j - 4]        * kernel[7]
            + input_buf[j - 4]  * kernel[8]
            - out[j - 5]        * kernel[9]
            + input_buf[j - 5]  * kernel[10]
            - out[j - 6]        * kernel[11]
            + input_buf[j - 6]  * kernel[12]
            - out[j - 7]        * kernel[13]
            + input_buf[j - 7]  * kernel[14]
            - out[j - 8]        * kernel[15]
            + input_buf[j - 8]  * kernel[16]
            - out[j - 9]        * kernel[17]
            + input_buf[j - 9]  * kernel[18]
            - out[j - 10]       * kernel[19]
            + input_buf[j - 10] * kernel[20]
        )
        out.append(val)
    return out[MAX_ORDER:]


def filter_butter(
    input_buf: list[float],
    output_pre: list[float],
    n_samples: int,
    kernel: tuple[float, ...],
) -> list[float]:
    """Apply 2nd-order Butterworth IIR filter.

    Args:
        input_buf:  Pre-buffer (MAX_ORDER values) followed by n_samples current
                    samples.  Only positions [-2] and [-1] relative to each
                    output sample are accessed, so MAX_ORDER pre-buffer depth
                    is more than sufficient.
        output_pre: Previous MAX_ORDER output values (pre-buffer only).
        n_samples:  Number of new samples to process.
        kernel:     5-element coefficient tuple (b0,a1,b1,a2,b2).

    Returns:
        List of n_samples output values.
    """
    out: list[float] = list(output_pre)
    for i in range(n_samples):
        j = MAX_ORDER + i
        val = (
            input_buf[j]      * kernel[0]
            - out[j - 1]      * kernel[1]
            + input_buf[j - 1] * kernel[2]
            - out[j - 2]      * kernel[3]
            + input_buf[j - 2] * kernel[4]
        )
        out.append(val)
    return out[MAX_ORDER:]
