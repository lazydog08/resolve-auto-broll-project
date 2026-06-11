from types import SimpleNamespace

import pytest

from auto_broll.config import Config
from auto_broll.models import DUPLICATE_MATCH, NO_MATCH, OK, STRETCHED, TextPlusGuide
from auto_broll.resolve.adapter import ResolveApiError
from auto_broll.pipeline import (
    decision_to_verify_record,
    _materialize_retime_for_placement,
    _set_current_timeline,
    _source_duration_for_timeline_placement,
    load_decisions_from_report,
    protected_track_snapshot,
    run_dry_run_with_guides,
)


def guide(shot_id):
    return TextPlusGuide("V2", 0, "Text+", 10, 20, 10, shot_id or "", shot_id, "StyledText")


def test_decision_to_verify_record_maps_dry_run_statuses(tmp_path):
    config = Config(out_dir=str(tmp_path), broll_dir=str(tmp_path))
    matched = tmp_path / "C001.mov"
    matched.write_text("fixture")

    records = run_dry_run_with_guides(
        [guide("001"), guide("002"), guide("003")],
        config,
        broll_paths=[str(matched)],
        run_metadata=SimpleNamespace(mode="dry-run"),
    )

    assert records[0].status == OK
    assert records[0].chosen_path == str(matched)
    assert records[1].status == NO_MATCH
    assert records[2].status == NO_MATCH


def test_decision_to_verify_record_preserves_duplicate_and_stretched_status(tmp_path):
    config = Config(out_dir=str(tmp_path), broll_dir=str(tmp_path))
    first = tmp_path / "a_C001.mov"
    second = tmp_path / "z_C001.mov"
    first.write_text("fixture")
    second.write_text("fixture")

    records = run_dry_run_with_guides(
        [guide("001")],
        config,
        broll_paths=[str(first), str(second)],
        source_durations={str(first): 5, str(second): 5},
        run_metadata=SimpleNamespace(mode="dry-run"),
    )

    assert records[0].status == STRETCHED
    assert "stretched" in records[0].detail.lower()

    records = run_dry_run_with_guides(
        [guide("001")],
        config,
        broll_paths=[str(first), str(second)],
        run_metadata=SimpleNamespace(mode="dry-run"),
    )

    assert records[0].status == DUPLICATE_MATCH
    assert records[0].chosen_path == str(first)


def test_dry_run_probes_source_duration_when_not_supplied(tmp_path, monkeypatch):
    config = Config(out_dir=str(tmp_path), broll_dir=str(tmp_path))
    matched = tmp_path / "C001.mov"
    matched.write_text("fixture")

    monkeypatch.setattr("auto_broll.pipeline.probe_video_frame_count", lambda path: 5)

    records = run_dry_run_with_guides(
        [guide("001")],
        config,
        broll_paths=[str(matched)],
        run_metadata=SimpleNamespace(mode="dry-run"),
    )

    assert records[0].status == STRETCHED
    assert records[0].source_duration_frames == 5


def test_decision_to_verify_record_maps_placeable_to_ok():
    from auto_broll.models import MatchDecision, PLANNED_OK

    decision = MatchDecision("001", guide("001"), "/broll/C001.mov", ["/broll/C001.mov"], PLANNED_OK, "single match")

    record = decision_to_verify_record(decision)

    assert record.status == OK
    assert record.actual_start is None
    assert record.intended_start == 10


def test_load_decisions_from_report_round_trips_report_json(tmp_path):
    report = tmp_path / "auto_broll_report.json"
    report.write_text(
        """
        {
          "decisions": [
            {
              "shot_id": "001",
              "guide": {
                "track": "V2",
                "item_index": 0,
                "name": "Text+",
                "start": 10,
                "end": 20,
                "duration": 10,
                "raw_text": "001",
                "normalized_shot_id": "001",
                "source": "StyledText"
              },
              "chosen_path": "/broll/C001.mov",
              "duplicate_candidates": ["/broll/C001.mov"],
              "status": "PLANNED_OK",
              "note": "single candidate matched this shot id",
              "source_duration": null
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    decisions = load_decisions_from_report(report)

    assert decisions[0].shot_id == "001"
    assert decisions[0].guide.start == 10
    assert decisions[0].chosen_path == "/broll/C001.mov"


class FakeSnapshotItem:
    def __init__(self, name, start, end):
        self.name = name
        self.start = start
        self.end = end

    def GetName(self):
        return self.name

    def GetStart(self):
        return self.start

    def GetEnd(self):
        return self.end

    def GetDuration(self):
        return self.end - self.start


class FakeSnapshotTimeline:
    def __init__(self):
        self.items = {
            1: [FakeSnapshotItem("A", 10, 20)],
            2: [FakeSnapshotItem("Text+", 30, 40)],
            3: [FakeSnapshotItem("B-roll", 50, 60)],
        }

    def GetItemListInTrack(self, track_type, track_index):
        return self.items.get(track_index, [])


def test_protected_track_snapshot_only_captures_v1_v2():
    snapshot = protected_track_snapshot(FakeSnapshotTimeline())

    assert [row["track"] for row in snapshot] == ["V1", "V2"]
    assert snapshot[0]["duration"] == 10


def test_materialize_retime_for_placement_generates_file_for_stretched_decision(tmp_path, monkeypatch):
    from auto_broll.models import MatchDecision, PlannedSegment

    source = tmp_path / "C896.MP4"
    source.write_text("fixture")
    guide_obj = guide("896")
    segment = PlannedSegment(
        guide=guide_obj,
        guide_index=0,
        segment_index=0,
        segment_count=1,
        segment_start=10,
        segment_end=212,
        segment_duration=202,
        shot_id_raw="896",
        shot_id_canonical="896",
    )
    decision = MatchDecision(
        "896",
        guide_obj,
        str(source),
        [str(source)],
        STRETCHED,
        "stretched",
        source_duration_frames=195,
        target_duration_frames=202,
        segment=segment,
    )
    generated = tmp_path / "generated.mp4"

    monkeypatch.setattr(
        "auto_broll.pipeline.generate_retimed_media",
        lambda source_path, output_dir, shot_id, source_frames, target_frames, timeline_fps: str(generated),
    )

    materialized = _materialize_retime_for_placement(decision, Config(generated_retime_dir=str(tmp_path)), 25.0)

    assert materialized.generated_retime_file == str(generated)
    assert materialized.retime_method == "generated"


def test_source_duration_for_timeline_placement_scales_offspeed_media():
    class FakeMediaItem:
        def GetClipProperty(self, key):
            return {"FPS": "119.88"}.get(key)

    assert _source_duration_for_timeline_placement(156, FakeMediaItem(), 59.94) == 312


class FakeNamedTimeline:
    def __init__(self, name):
        self.name = name

    def GetName(self):
        return self.name


class FakeProjectWithStaleCurrentTimeline:
    def __init__(self):
        self.original = FakeNamedTimeline("Original")
        self.current = self.original

    def SetCurrentTimeline(self, timeline):
        return True

    def GetCurrentTimeline(self):
        return self.current


def test_set_current_timeline_rejects_truthy_but_stale_resolve_switch():
    project = FakeProjectWithStaleCurrentTimeline()
    duplicate = FakeNamedTimeline("Original__AUTO_BROLL_v001")

    with pytest.raises(ResolveApiError, match="current timeline mismatch"):
        _set_current_timeline(project, duplicate)
