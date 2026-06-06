"""Parse manual B-roll override CSV files."""

from __future__ import annotations

import csv

from auto_broll.core.shot_parser import parse_shot_ids


def parse_override_csv(path: str, pad_width: int = 3) -> dict[str, str]:
    """Parse a CSV with exact ``shot_id,path`` columns into normalized overrides."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if [field.strip() for field in fieldnames] != ["shot_id", "path"]:
            raise ValueError("override CSV must have shot_id,path columns")

        overrides: dict[str, str] = {}
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"override CSV row {line_number} has unexpected extra fields")

            raw_shot_id = (row.get("shot_id") or "").strip()
            override_path = (row.get("path") or "").strip()
            parsed_ids = parse_shot_ids(raw_shot_id, pad_width=pad_width)
            shot_id = parsed_ids[0] if parsed_ids else None
            if shot_id is None or not override_path:
                raise ValueError(f"override CSV row {line_number} must include parseable shot_id and path")
            if shot_id in overrides:
                raise ValueError(f"override CSV row {line_number} duplicates shot_id {shot_id}")

            overrides[shot_id] = override_path

    return overrides
