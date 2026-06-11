import pytest

from auto_broll.core.shot_parser import normalize, parse_shot_ids


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("001", "001"),
        ("C001", "001"),
        ("shot 001", "001"),
        ("镜头001", "001"),
        (" Shot: C7 ", "007"),
        ("镜头：12。备用", "012"),
    ],
)
def test_normalize_accepts_common_textplus_shot_labels(raw_text, expected):
    assert normalize(raw_text) == expected


def test_normalize_uses_first_digit_run_and_configurable_padding():
    assert normalize("镜头 2 / version 12", pad_width=4) == "0002"


@pytest.mark.parametrize("raw_text", ["", "镜头", "shot abc", "no guide here"])
def test_normalize_returns_none_when_no_number_exists(raw_text):
    assert normalize(raw_text) is None


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("888", ["888"]),
        ("5248", ["5248"]),
        ("888 889", ["888", "889"]),
        ("5248 5249", ["5248", "5249"]),
        ("888,889", ["888", "889"]),
        ("888、889", ["888", "889"]),
        ("888/889", ["888", "889"]),
        ("C888 C889", ["888", "889"]),
        ("C0888 C0889", ["888", "889"]),
        ("镜头888 镜头889", ["888", "889"]),
        ("shot 888 shot 889", ["888", "889"]),
        ("5248 备注", ["5248"]),
        ("备注 5248", ["5248"]),
        ("5248 数据", ["5248"]),
        ("数据 5248", ["5248"]),
        ("5248 动效", ["5248"]),
        ("888 889 数据", ["888", "889"]),
        ("备注\n5248\n5249", ["5248", "5249"]),
        ("5318 19", ["5318", "5319"]),
        ("5318/19", ["5318", "5319"]),
        ("531819", ["5318", "5319"]),
        ("6348/49", ["6348", "6349"]),
        ("6348 49", ["6348", "6349"]),
        ("9998/99", ["9998", "9999"]),
        ("7976-7980", ["7976", "7977", "7978", "7979", "7980"]),
        ("C7976-C7980", ["7976", "7977", "7978", "7979", "7980"]),
        ("镜头7976-7980", ["7976", "7977", "7978", "7979", "7980"]),
    ],
)
def test_parse_shot_ids_returns_ordered_numeric_tag_ids(raw_text, expected):
    assert parse_shot_ids(raw_text) == expected


@pytest.mark.parametrize(
    "raw_text",
    [
        "数据",
        "动效",
        "图表",
        "animation",
        "motion graphics",
        "需要补数据",
        "这里做动效",
        "2026年数据",
        "数据2026",
        "50%",
        "1080p",
        "v2",
        "图表01",
        "5248A",
        "A5248",
    ],
)
def test_parse_shot_ids_ignores_annotation_and_embedded_numbers(raw_text):
    assert parse_shot_ids(raw_text) == []
