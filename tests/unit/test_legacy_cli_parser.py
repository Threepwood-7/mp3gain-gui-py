from __future__ import annotations

import pytest

from mp3gain_gui_py.legacy_cli import _parse_legacy_args


def test_parse_supports_slash_dash_and_attached_values() -> None:
    args = _parse_legacy_args(
        ["/q", "-o", "/d1.5", "-m-2", "/g4", "sample.mp3"],
    )
    assert args.quiet is True
    assert args.table_output is True
    assert args.db_mod == 1.5
    assert args.mp3_gain_mod == -2
    assert args.direct_gain_steps == 4
    assert args.files[0].name == "sample.mp3"


def test_r_a_precedence_last_wins() -> None:
    album = _parse_legacy_args(["/r", "/a", "sample.mp3"])
    track = _parse_legacy_args(["/a", "/r", "sample.mp3"])
    assert album.apply_mode == "album"
    assert track.apply_mode == "track"


@pytest.mark.parametrize(
    ("argv", "policy", "delete_requested", "tag_format"),
    [
        (["/s", "c", "sample.mp3"], "check_only", False, "apev2"),
        (["/s", "s", "sample.mp3"], "skip", False, "apev2"),
        (["/s", "r", "sample.mp3"], "recalc", False, "apev2"),
        (["/s", "d", "sample.mp3"], "auto", True, "apev2"),
        (["/s", "i", "sample.mp3"], "auto", False, "id3"),
        (["/s", "a", "sample.mp3"], "auto", False, "apev2"),
        (["/s", "d", "/s", "i", "sample.mp3"], "auto", True, "id3"),
    ],
)
def test_parse_s_modes(
    argv: list[str],
    policy: str,
    delete_requested: bool,
    tag_format: str,
) -> None:
    args = _parse_legacy_args(argv)
    assert args.stored_tag_policy == policy
    assert args.delete_tags_requested is delete_requested
    assert args.tag_format == tag_format


def test_parse_unsupported_s_mode_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported /s mode"):
        _parse_legacy_args(["/s", "z", "sample.mp3"])


def test_parse_l_separated_values() -> None:
    args = _parse_legacy_args(["/l", "1", "-3", "sample.mp3"])
    assert args.single_channel is not None
    assert args.single_channel.channel_index == 1
    assert args.single_channel.steps == -3


def test_parse_qmark_sets_help_qmark_mode() -> None:
    args = _parse_legacy_args(["/?", "wrap"])
    assert args.info_mode == "help_qmark"
    assert args.info_topic == "wrap"
