from __future__ import annotations

import math
import random

import pytest

from mp3gain_gui_py._legacy_exact.math import (
    db_to_legacy_steps,
    legacy_round_to_int,
    legacy_steps_to_db_approx,
    legacy_steps_to_db_exact,
)

from ._c_oracle import CTagState, c_oracle_available, load_c_oracle


def _require_oracle() -> object:
    if not c_oracle_available():
        pytest.skip("C oracle unavailable: missing gcc or oracle source file")
    return load_c_oracle()


def _python_tag_update(
    tag: CTagState, left: int, right: int, wrap_gain: int
) -> CTagState:
    if left == 0 and right == 0:
        return tag

    if not tag.have_undo:
        tag.undo_left = 0
        tag.undo_right = 0
    tag.dirty = 1
    tag.undo_right -= right
    tag.undo_left -= left
    tag.undo_wrap = wrap_gain
    tag.have_undo = 1

    if left != right:
        return tag

    step = left
    dbl_gain_change = step * 1.505
    peak_mult = math.pow(2.0, step / 4.0)

    if tag.have_track_gain:
        tag.track_gain -= dbl_gain_change
    if tag.have_track_peak:
        tag.track_peak *= peak_mult
    if tag.have_album_gain:
        tag.album_gain -= dbl_gain_change
    if tag.have_album_peak:
        tag.album_peak *= peak_mult

    if tag.have_minmax_gain:
        cur_min = tag.min_gain + step
        cur_max = tag.max_gain + step
        if wrap_gain:
            if cur_min < 0 or cur_min > 255 or cur_max < 0 or cur_max > 255:
                tag.have_minmax_gain = 0
        else:
            if tag.min_gain == 0 or cur_min < 0:
                tag.min_gain = 0
            elif cur_min > 255:
                tag.min_gain = 255
            else:
                tag.min_gain = cur_min
            tag.max_gain = 0 if cur_max < 0 else 255 if cur_max > 255 else cur_max

    if tag.have_album_minmax_gain:
        cur_min = tag.album_min_gain + step
        cur_max = tag.album_max_gain + step
        if wrap_gain:
            if cur_min < 0 or cur_min > 255 or cur_max < 0 or cur_max > 255:
                tag.have_album_minmax_gain = 0
        else:
            if tag.album_min_gain == 0 or cur_min < 0:
                tag.album_min_gain = 0
            elif cur_min > 255:
                tag.album_min_gain = 255
            else:
                tag.album_min_gain = cur_min
            tag.album_max_gain = 0 if cur_max < 0 else 255 if cur_max > 255 else cur_max

    return tag


def _as_tuple(tag: CTagState) -> tuple[object, ...]:
    return (
        tag.dirty,
        tag.have_undo,
        tag.undo_left,
        tag.undo_right,
        tag.undo_wrap,
        tag.have_track_gain,
        round(tag.track_gain, 9),
        tag.have_track_peak,
        round(tag.track_peak, 9),
        tag.have_album_gain,
        round(tag.album_gain, 9),
        tag.have_album_peak,
        round(tag.album_peak, 9),
        tag.have_minmax_gain,
        tag.min_gain,
        tag.max_gain,
        tag.have_album_minmax_gain,
        tag.album_min_gain,
        tag.album_max_gain,
    )


def test_rounding_matches_c_oracle() -> None:
    oracle = _require_oracle()
    values = [
        -12.6,
        -12.5,
        -12.49,
        -0.51,
        -0.5,
        -0.49,
        0.0,
        0.49,
        0.5,
        0.51,
        12.49,
        12.5,
        12.6,
    ]
    for value in values:
        assert legacy_round_to_int(value) == oracle.mp3gain_c_legacy_round(value)


def test_db_to_steps_matches_c_oracle_randomized() -> None:
    oracle = _require_oracle()
    rng = random.Random(7331)
    for _ in range(500):
        db_gain = rng.uniform(-30.0, 30.0)
        mod = rng.randint(-8, 8)
        py_steps = db_to_legacy_steps(db_gain, mp3_gain_mod=mod)
        c_steps = oracle.mp3gain_c_db_to_steps(db_gain, mod)
        assert py_steps == c_steps


def test_steps_to_db_conversions_match_c_oracle() -> None:
    oracle = _require_oracle()
    for steps in range(-30, 31):
        py_exact = legacy_steps_to_db_exact(steps)
        c_exact = oracle.mp3gain_c_steps_to_db_exact(steps)
        assert abs(py_exact - c_exact) < 1e-12

        py_approx = legacy_steps_to_db_approx(steps)
        c_approx = oracle.mp3gain_c_steps_to_db_approx(steps)
        assert abs(py_approx - c_approx) < 1e-12


def test_autoclip_track_formula_matches_c_oracle_known_values() -> None:
    oracle = _require_oracle()
    cases = [
        (6, 33973.501952),
        (2, 32000.0),
        (-5, 33973.501952),
        (4, 0.0),
    ]
    for requested, max_sample in cases:
        if max_sample <= 0.0:
            expected = requested
        else:
            max_no_clip = math.floor(
                4.0 * math.log10(32767.0 / max_sample) / math.log10(2.0)
            )
            expected = min(requested, int(max_no_clip))
        assert oracle.mp3gain_c_autoclip_track_gain(requested, max_sample) == expected


def test_autoclip_album_formula_matches_c_oracle_known_values() -> None:
    oracle = _require_oracle()
    assert oracle.mp3gain_c_autoclip_album_gain(6, 1.169319) == -1
    assert oracle.mp3gain_c_autoclip_album_gain(1, 1.169319) == -1
    assert oracle.mp3gain_c_autoclip_album_gain(-2, 1.169319) == -2
    assert oracle.mp3gain_c_autoclip_album_gain(4, 0.0) == 4


def test_tag_update_python_mirror_matches_c_oracle() -> None:
    oracle = _require_oracle()
    base = CTagState(
        dirty=0,
        have_undo=0,
        undo_left=0,
        undo_right=0,
        undo_wrap=0,
        have_track_gain=1,
        track_gain=-9.21,
        have_track_peak=1,
        track_peak=1.036789,
        have_album_gain=1,
        album_gain=-9.35,
        have_album_peak=1,
        album_peak=1.169319,
        have_minmax_gain=1,
        min_gain=82,
        max_gain=210,
        have_album_minmax_gain=1,
        album_min_gain=38,
        album_max_gain=210,
    )

    scenarios = [
        (6, 6, 0),
        (6, 6, 1),
        (-4, -4, 0),
        (0, 3, 0),
        (3, 0, 0),
    ]
    for left, right, wrap in scenarios:
        py_state = CTagState(*_as_tuple(base))
        c_state = CTagState(*_as_tuple(base))
        _python_tag_update(py_state, left, right, wrap)
        oracle.mp3gain_c_update_tag_state(c_state, left, right, wrap)
        assert _as_tuple(py_state) == _as_tuple(c_state)
