from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_broll import __version__


VERIFY_CSV_COLUMNS = [
    "guide_index",
    "guide_raw_text",
    "guide_start",
    "guide_end",
    "guide_duration",
    "parsed_shot_ids",
    "segment_index",
    "segment_count",
    "segment_start",
    "segment_end",
    "segment_duration",
    "shot_id_raw",
    "shot_id_canonical",
    "shot_id",
    "status",
    "intended_start",
    "actual_start",
    "intended_duration",
    "actual_duration",
    "chosen_path",
    "matched_file",
    "all_candidates",
    "source_duration_frames",
    "target_duration_frames",
    "speed_percent",
    "retime_method",
    "generated_retime_file",
    "placed_track_index",
    "placed_item_name",
    "placed_start",
    "placed_duration",
    "error_message",
    "detail",
]


@dataclass(frozen=True)
class RunMetadata:
    mode: str
    timeline_name: str | None = None
    duplicate_name: str | None = None
    broll_dir: str | None = None
    out_dir: str | None = None
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    tool_version: str = __version__


def build_report(
    run_metadata: Any,
    guides: list[Any],
    decisions: list[Any],
    placements: list[Any],
    verify_records: list[Any],
    v1_v2_unchanged: bool | None,
) -> dict[str, Any]:
    return {
        "run_metadata": _to_jsonable(run_metadata),
        "guides": _to_jsonable(guides),
        "decisions": _to_jsonable(decisions),
        "placements": _to_jsonable(placements),
        "verify_records": _to_jsonable(verify_records),
        "v1_v2_unchanged": v1_v2_unchanged,
    }


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_to_jsonable(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dict__"):
        return _to_jsonable(vars(value))
    return value
