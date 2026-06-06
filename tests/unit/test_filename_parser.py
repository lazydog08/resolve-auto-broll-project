import pytest

from auto_broll.core.filename_parser import DEFAULT_PATTERN, canonicalize_shot_id, extract_shot_id


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("C001.mov", "1"),
        ("C0001.mov", "1"),
        ("20260605_C0888_take2.mov", "888"),
        ("broll-C12.mp4", "12"),
        ("folder/c007.MXF", "7"),
        ("C5248.MP4", "5248"),
    ],
)
def test_extract_shot_id_matches_explicit_c_digit_tokens(filename, expected):
    assert extract_shot_id(filename, DEFAULT_PATTERN, pad_width=3) == expected


@pytest.mark.parametrize(
    "filename",
    [
        "20260605.mov",
        "CARD_0007.mov",
        "CAM2_take1.mov",
        "camera2_take1.mp4",
        "CARD_COVER_0007.mov",
        "XC001.mov",
        "C001A.mov",
    ],
)
def test_extract_shot_id_rejects_non_explicit_c_digit_numbers(filename):
    assert extract_shot_id(filename, DEFAULT_PATTERN, pad_width=3) is None


def test_canonicalize_shot_id_strips_insignificant_leading_zeroes():
    assert canonicalize_shot_id("001") == "1"
    assert canonicalize_shot_id("0888") == "888"
    assert canonicalize_shot_id("05248") == "5248"
