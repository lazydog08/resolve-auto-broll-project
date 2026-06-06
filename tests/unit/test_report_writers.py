from __future__ import annotations

import csv
import json

from auto_broll.models import (
    MISSING,
    OK,
    PLANNED_OK,
    MatchDecision,
    PlacementResult,
    TextPlusGuide,
    VerifyRecord,
)
from auto_broll.report.schema import VERIFY_CSV_COLUMNS
from auto_broll.report.writers import write_reports


def _sample_records():
    guide = TextPlusGuide(
        track="V2",
        item_index=0,
        name="Text+ 001",
        start=10,
        end=40,
        duration=30,
        raw_text="镜头001",
        normalized_shot_id="001",
        source="StyledText",
    )
    decision = MatchDecision(
        shot_id="001",
        guide=guide,
        chosen_path="/broll/C001.mov",
        duplicate_candidates=[],
        status=PLANNED_OK,
        note="single match",
        source_duration=90,
    )
    placement = PlacementResult("001", 10, 30, True, True, None)
    ok = VerifyRecord("001", OK, 10, 10, 30, 30, "/broll/C001.mov", "matched")
    missing = VerifyRecord("002", MISSING, 50, None, 20, None, None, "no readback clip")
    return guide, decision, placement, ok, missing


def test_write_reports_creates_json_csv_and_summary(tmp_path):
    guide, decision, placement, ok, missing = _sample_records()

    paths = write_reports(
        tmp_path / "nested" / "reports",
        run_metadata={"mode": "dry-run", "timeline_name": "Timeline 1"},
        guides=[guide],
        decisions=[decision],
        placements=[placement],
        verify_records=[ok, missing],
        v1_v2_unchanged=True,
    )

    assert paths["json"].name == "auto_broll_report.json"
    assert paths["csv"].name == "auto_broll_report.csv"
    assert paths["summary"].name == "auto_broll_summary.txt"
    assert all(path.exists() for path in paths.values())

    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["run_metadata"]["mode"] == "dry-run"
    assert data["guides"][0]["raw_text"] == "镜头001"
    assert data["decisions"][0]["guide"]["normalized_shot_id"] == "001"
    assert data["placements"][0]["api_ok"] is True
    assert data["verify_records"][1]["status"] == MISSING
    assert data["v1_v2_unchanged"] is True

    with paths["csv"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0].keys() == set(VERIFY_CSV_COLUMNS)
    assert len(rows) == 2
    assert rows[0]["shot_id"] == "001"
    assert "guide_raw_text" in rows[0]
    assert "segment_start" in rows[0]
    assert "retime_method" in rows[0]
    assert rows[1]["actual_start"] == ""
    assert rows[1]["chosen_path"] == ""

    summary = paths["summary"].read_text(encoding="utf-8")
    assert "Total verify records: 2" in summary
    assert "OK: 1" in summary
    assert "MISSING: 1" in summary
    assert "V1/V2 unchanged: true" in summary
    assert "Non-OK details" in summary
    assert "002 | MISSING | no readback clip" in summary
