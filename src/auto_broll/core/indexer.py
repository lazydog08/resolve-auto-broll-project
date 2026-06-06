"""Build a B-roll lookup index from paths."""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING

from auto_broll.core.filename_parser import DEFAULT_PATTERN, canonicalize_shot_id, extract_raw_shot_id

if TYPE_CHECKING:
    from auto_broll.models import BrollCandidate


def build_index(
    paths: Iterable[str],
    pattern: str = DEFAULT_PATTERN,
    pad_width: int = 3,
) -> dict[str, list["BrollCandidate"]]:
    """Group B-roll file paths by normalized shot id."""
    from auto_broll.models import BrollCandidate

    grouped: dict[str, list[BrollCandidate]] = defaultdict(list)
    for path in _iter_files(paths):
        raw_shot_id = extract_raw_shot_id(os.path.basename(path), pattern)
        shot_id = canonicalize_shot_id(raw_shot_id)
        if shot_id is None or raw_shot_id is None:
            continue
        grouped[shot_id].append(
            BrollCandidate(
                shot_id=shot_id,
                path=path,
                filename=os.path.basename(path),
                shot_id_raw=raw_shot_id,
                shot_id_canonical=shot_id,
            )
        )

    return {
        shot_id: sorted(candidates, key=lambda candidate: candidate.path)
        for shot_id, candidates in sorted(grouped.items())
    }


def _iter_files(paths: Iterable[str]) -> Iterable[str]:
    for raw_path in sorted(str(path) for path in paths):
        if os.path.isdir(raw_path):
            for root, dirs, files in os.walk(raw_path):
                dirs.sort()
                for filename in sorted(files):
                    path = os.path.join(root, filename)
                    if os.path.isfile(path):
                        yield path
        elif os.path.isfile(raw_path):
            yield raw_path
