"""Parse Text+ tag strings into shot ids."""

from __future__ import annotations

import re

from auto_broll.core.filename_parser import canonicalize_shot_id

_C_PREFIXED_ID = re.compile(r"(?<![A-Za-z0-9])C0*(\d{1,5})(?![A-Za-z0-9])", re.IGNORECASE)
_LABELED_ID = re.compile(
    r"(?i)(?:shot|clip|镜头)\s*[:：#-]?\s*C?0*(\d{1,5})(?![A-Za-z0-9])"
)
_RANGE_ID = re.compile(
    r"(?<![A-Za-z0-9])C?0*(\d{3,5})\s*[-~～—]\s*C?0*(\d{3,5})(?![A-Za-z0-9\u4e00-\u9fff%])",
    re.IGNORECASE,
)
_ABBREVIATED_PAIR = re.compile(r"(?<![A-Za-z0-9\u4e00-\u9fff])(\d{4})\s*[/、,，\s]\s*(\d{2})(?![A-Za-z0-9\u4e00-\u9fff%])")
_COMPACT_PAIR = re.compile(r"(?<![A-Za-z0-9\u4e00-\u9fff])(\d{4})(\d{2})(?![A-Za-z0-9\u4e00-\u9fff%])")
_BARE_NUMERIC_ID = re.compile(r"(?<![A-Za-z0-9\u4e00-\u9fff])(\d{3,5})(?![A-Za-z0-9\u4e00-\u9fff%])")


def normalize(raw_text: str, pad_width: int = 3) -> str | None:
    """Return the first parsed shot id padded for older call sites."""
    shot_ids = parse_shot_ids(raw_text)
    if not shot_ids:
        return None
    return shot_ids[0].zfill(pad_width)


def parse_shot_ids(raw_text: str | None, pad_width: int = 3) -> list[str]:
    """Return ordered canonical shot ids from a Text+ tag string."""
    if raw_text is None:
        return []

    text = str(raw_text).strip()
    if not text:
        return []

    matches: list[tuple[int, int, int, str]] = []
    for match in _RANGE_ID.finditer(text):
        expanded = _expand_range(match.group(1), match.group(2))
        for shot_id in expanded:
            matches.append((match.start(), match.end(), 0, shot_id))

    for pattern in (_ABBREVIATED_PAIR, _COMPACT_PAIR):
        for match in pattern.finditer(text):
            first = canonicalize_shot_id(match.group(1))
            second = _expand_two_digit_suffix(match.group(1), match.group(2))
            if first is None or second is None:
                continue
            matches.append((match.start(1), match.end(1), 1, first))
            matches.append((match.start(2), match.end(2), 1, second))

    for pattern in (_LABELED_ID, _C_PREFIXED_ID, _BARE_NUMERIC_ID):
        for match in pattern.finditer(text):
            shot_id = canonicalize_shot_id(match.group(1))
            if shot_id is None:
                continue
            matches.append((match.start(1), match.end(1), 2, shot_id))

    ordered: list[tuple[int, int, str]] = []
    for start, end, _priority, shot_id in sorted(matches, key=lambda item: (item[0], item[2], item[1])):
        if any((start, end, shot_id) == existing for existing in ordered):
            continue
        if any(
            _spans_overlap((start, end), (existing_start, existing_end)) and (start, end) != (existing_start, existing_end)
            for existing_start, existing_end, _ in ordered
        ):
            continue
        ordered.append((start, end, shot_id))

    return [shot_id for _, _, shot_id in ordered]


def _spans_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _expand_two_digit_suffix(prefix_source: str, suffix: str) -> str | None:
    if len(prefix_source) < 3 or len(suffix) != 2 or not prefix_source.isdigit() or not suffix.isdigit():
        return None
    return canonicalize_shot_id(prefix_source[:-2] + suffix)


def _expand_range(start: str, end: str) -> list[str]:
    first = canonicalize_shot_id(start)
    last = canonicalize_shot_id(end)
    if first is None or last is None:
        return []

    first_value = int(first)
    last_value = int(last)
    if last_value < first_value:
        return []

    return [str(value) for value in range(first_value, last_value + 1)]
