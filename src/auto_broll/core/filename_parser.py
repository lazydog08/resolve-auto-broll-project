"""Extract shot ids from B-roll filenames."""

from __future__ import annotations

import os
import re

DEFAULT_PATTERN = r"(?i)(?<![A-Za-z0-9])(?:A|C)(\d{1,5})(?![A-Za-z0-9])"


def extract_shot_id(
    filename: str,
    pattern: str = DEFAULT_PATTERN,
    pad_width: int = 3,
) -> str | None:
    """Return a normalized id from an explicit camera shot filename token."""
    basename = os.path.basename(filename)
    match = re.search(pattern or DEFAULT_PATTERN, basename)
    if match is None:
        return None

    raw_id = extract_raw_shot_id(filename, pattern)
    if raw_id is None:
        return None

    return canonicalize_shot_id(raw_id)


def extract_raw_shot_id(
    filename: str,
    pattern: str = DEFAULT_PATTERN,
) -> str | None:
    """Return raw digits from an explicit ``A<digits>`` or ``C<digits>`` filename token."""
    basename = os.path.basename(filename)
    match = re.search(pattern or DEFAULT_PATTERN, basename)
    if match is None:
        return None

    digit_match = _first_group_with_span(match)
    if digit_match is None:
        return None

    digits, span = digit_match
    if not _is_explicit_camera_token(basename, span):
        return None

    return digits


def canonicalize_shot_id(raw_id: str | int | None) -> str | None:
    """Normalize a numeric id for matching by value, not padding width."""
    if raw_id is None:
        return None
    text = str(raw_id).strip()
    if not text.isdigit():
        return None
    return str(int(text))


def _first_group_with_span(match: re.Match[str]) -> tuple[str, tuple[int, int]] | None:
    for index, group in enumerate(match.groups(), start=1):
        if group:
            return group, match.span(index)
    return None


def _is_explicit_camera_token(text: str, digit_span: tuple[int, int]) -> bool:
    start, end = digit_span
    prefix_index = start - 1
    if prefix_index < 0 or text[prefix_index].lower() not in {"a", "c"}:
        return False
    if prefix_index > 0 and text[prefix_index - 1].isalnum():
        return False
    if end < len(text) and text[end].isalnum():
        return False
    return True
