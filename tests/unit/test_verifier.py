from auto_broll.core.verifier import verify_decisions
from auto_broll.models import (
    API_FAILED,
    IGNORED_NON_SHOT_TEXT,
    MISSING,
    NO_MATCH,
    OK,
    PLANNED_OK,
    SHORT_SOURCE,
    STRETCHED,
    WRONG_DURATION,
    MatchDecision,
    PlannedSegment,
    ReadBackClip,
    TextPlusGuide,
)


def guide(shot_id="001", start=100, duration=30):
    return TextPlusGuide(
        "V2",
        0,
        "Text+",
        start,
        start + duration,
        duration,
        shot_id or "备注",
        shot_id,
        "StyledText",
        parsed_shot_ids=[shot_id] if shot_id else [],
    )


def segment(shot_id="001", start=100, duration=30, guide_obj=None, segment_index=0, segment_count=1):
    guide_obj = guide_obj or guide(shot_id, start=start, duration=duration)
    return PlannedSegment(
        guide=guide_obj,
        guide_index=guide_obj.item_index,
        segment_index=segment_index,
        segment_count=segment_count,
        segment_start=start,
        segment_end=start + duration,
        segment_duration=duration,
        shot_id_raw=shot_id,
        shot_id_canonical=shot_id,
    )


def decision(status=PLANNED_OK, shot_id="001", path="/broll/C001.mov"):
    guide_obj = guide(shot_id)
    return MatchDecision(shot_id, guide_obj, path, [path] if path else [], status, "note", segment=segment(shot_id, guide_obj=guide_obj))


def clip(start=100, duration=30, path="/broll/C001.mov", name="C001.mov"):
    return ReadBackClip("AUTO_BROLL", name, start, start + duration, duration, path)


def test_verify_decisions_reports_ok_when_readback_matches_exactly():
    records = verify_decisions([decision()], [clip()])

    assert records[0].status == OK
    assert records[0].actual_start == 100
    assert records[0].actual_duration == 30


def test_verify_decisions_reports_missing_when_no_clip_at_start():
    records = verify_decisions([decision()], [])

    assert records[0].status == MISSING
    assert "no AUTO_BROLL" in records[0].detail


def test_verify_decisions_reports_wrong_duration():
    records = verify_decisions([decision()], [clip(duration=31)])

    assert records[0].status == WRONG_DURATION
    assert records[0].actual_duration == 31


def test_verify_decisions_reports_api_failed_for_wrong_file_or_duplicate_readback():
    wrong_file = verify_decisions([decision()], [clip(path="/broll/C009.mov", name="C009.mov")])
    duplicate = verify_decisions([decision()], [clip(), clip()])

    assert wrong_file[0].status == API_FAILED
    assert "does not match chosen path" in wrong_file[0].detail
    assert duplicate[0].status == API_FAILED
    assert "multiple" in duplicate[0].detail


def test_verify_decisions_accepts_custom_override_filename_when_path_matches():
    custom = decision(path="/manual/my_shot.mov")
    records = verify_decisions([custom], [clip(path="/manual/my_shot.mov", name="my_shot.mov")])

    assert records[0].status == OK


def test_verify_decisions_carries_non_placeable_statuses():
    records = verify_decisions(
        [decision(status=NO_MATCH, path=None), decision(status=SHORT_SOURCE)],
        [clip()],
    )

    assert records[0].status == NO_MATCH
    assert records[1].status == SHORT_SOURCE


def test_verify_decisions_preserves_stretched_status_when_readback_matches():
    stretched = decision(status=STRETCHED)
    records = verify_decisions([stretched], [clip()])

    assert records[0].status == STRETCHED
    assert records[0].placed_duration == 30
    assert records[0].segment_start == 100


def test_verify_decisions_accepts_generated_retime_file_for_original_source():
    guide_obj = guide("896")
    generated = MatchDecision(
        "896",
        guide_obj,
        "/broll/C896.MP4",
        ["/broll/C896.MP4"],
        STRETCHED,
        "generated retime",
        generated_retime_file="/tmp/generated/C896_202.mov",
        segment=segment("896", guide_obj=guide_obj),
    )

    records = verify_decisions([generated], [clip(path="/tmp/generated/C896_202.mov", name="C896_202.mov")])

    assert records[0].status == STRETCHED


def test_verify_decisions_ignores_annotation_rows_without_placement():
    annotation = guide(None, start=200, duration=20)
    ignored = MatchDecision(
        None,
        annotation,
        None,
        [],
        IGNORED_NON_SHOT_TEXT,
        "annotation-only Text+ ignored",
        segment=PlannedSegment(
            guide=annotation,
            guide_index=annotation.item_index,
            segment_index=0,
            segment_count=0,
            segment_start=200,
            segment_end=220,
            segment_duration=20,
            shot_id_raw=None,
            shot_id_canonical=None,
            ignored_non_shot_text=True,
            guide_status=IGNORED_NON_SHOT_TEXT,
        ),
    )

    records = verify_decisions([ignored], [])

    assert records[0].status == IGNORED_NON_SHOT_TEXT
    assert records[0].matched_file is None
    assert records[0].segment_count == 0


def test_verify_decisions_reports_missing_only_for_the_missing_multi_shot_slice():
    guide_obj = guide("888", start=100, duration=203)
    first = MatchDecision(
        "888",
        guide_obj,
        "/broll/C888.MP4",
        ["/broll/C888.MP4"],
        PLANNED_OK,
        "match",
        segment=segment("888", start=100, duration=102, guide_obj=guide_obj, segment_index=0, segment_count=2),
    )
    second = MatchDecision(
        "889",
        guide_obj,
        "/broll/C889.MP4",
        ["/broll/C889.MP4"],
        PLANNED_OK,
        "match",
        segment=segment("889", start=202, duration=101, guide_obj=guide_obj, segment_index=1, segment_count=2),
    )

    records = verify_decisions([first, second], [clip(start=100, duration=102, path="/broll/C888.MP4", name="C888.MP4")])

    assert [record.status for record in records] == [OK, MISSING]
    assert records[1].segment_start == 202
