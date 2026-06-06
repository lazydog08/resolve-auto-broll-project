from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from auto_broll.models import (
    API_FAILED,
    COLLISION,
    DUPLICATE_MATCH,
    IGNORED_NON_SHOT_TEXT,
    MISSING,
    NO_MATCH,
    OFFLINE_MEDIA,
    OK,
    SHORT_SOURCE,
    STRETCHED,
    STRETCHED_HEAVY,
    STRETCH_FAILED,
    STRETCH_DISABLED,
    WRONG_DURATION,
)
from auto_broll.report.schema import VERIFY_CSV_COLUMNS, build_report


REPORT_JSON = "auto_broll_report.json"
REPORT_CSV = "auto_broll_report.csv"
REPORT_SUMMARY = "auto_broll_summary.txt"

_SUMMARY_STATUS_ORDER = [
    OK,
    STRETCHED,
    STRETCHED_HEAVY,
    STRETCH_FAILED,
    STRETCH_DISABLED,
    IGNORED_NON_SHOT_TEXT,
    MISSING,
    OFFLINE_MEDIA,
    NO_MATCH,
    DUPLICATE_MATCH,
    SHORT_SOURCE,
    WRONG_DURATION,
    COLLISION,
    API_FAILED,
]


def write_reports(
    out_dir: str | Path,
    run_metadata: Any,
    guides: list[Any],
    decisions: list[Any],
    placements: list[Any],
    verify_records: list[Any],
    v1_v2_unchanged: bool | None,
) -> dict[str, Path]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "json": output_dir / REPORT_JSON,
        "csv": output_dir / REPORT_CSV,
        "summary": output_dir / REPORT_SUMMARY,
    }

    write_json(paths["json"], run_metadata, guides, decisions, placements, verify_records, v1_v2_unchanged)
    write_csv(paths["csv"], verify_records)
    write_summary(paths["summary"], verify_records, v1_v2_unchanged)

    return paths


def write_json(
    path: str | Path,
    run_metadata: Any,
    guides: list[Any],
    decisions: list[Any],
    placements: list[Any],
    verify_records: list[Any],
    v1_v2_unchanged: bool | None,
) -> Path:
    report = build_report(run_metadata, guides, decisions, placements, verify_records, v1_v2_unchanged)
    output_path = Path(path)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return output_path


def write_csv(path: str | Path, verify_records: list[Any]) -> Path:
    output_path = Path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=VERIFY_CSV_COLUMNS)
        writer.writeheader()
        for record in verify_records:
            record_dict = build_report({}, [], [], [], [record], None)["verify_records"][0]
            writer.writerow({column: _csv_value(record_dict.get(column)) for column in VERIFY_CSV_COLUMNS})
    return output_path


def write_summary(path: str | Path, verify_records: list[Any], v1_v2_unchanged: bool | None) -> Path:
    output_path = Path(path)
    counts = Counter(record.status for record in verify_records)
    non_ok_records = [record for record in verify_records if record.status != OK]

    lines = [
        "Auto B-roll Summary",
        f"Total verify records: {len(verify_records)}",
        f"V1/V2 unchanged: {_bool_text(v1_v2_unchanged)}",
        "",
        "Status counts:",
    ]
    for status in _SUMMARY_STATUS_ORDER:
        lines.append(f"{status}: {counts.get(status, 0)}")

    lines.extend(["", "Non-OK details:"])
    if non_ok_records:
        for record in non_ok_records:
            shot_id = record.shot_id_canonical or record.shot_id or ""
            lines.append(f"{shot_id} | {record.status} | {record.error_message or record.detail}")
    else:
        lines.append("none")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return value


def _bool_text(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return str(value).lower()
