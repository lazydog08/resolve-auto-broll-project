from auto_broll.core.matcher import decide_matches
from auto_broll.models import (
    DUPLICATE_MATCH,
    IGNORED_NON_SHOT_TEXT,
    NO_MATCH,
    OVERRIDE,
    PLANNED_OK,
    STRETCHED,
    STRETCHED_HEAVY,
    STRETCH_DISABLED,
    UNPARSEABLE,
    BrollCandidate,
    TextPlusGuide,
)


def guide(shot_id, duration=30, raw_text=None, parsed_shot_ids=None):
    return TextPlusGuide(
        track="V2",
        item_index=0,
        name="Text+",
        start=100,
        end=100 + duration,
        duration=duration,
        raw_text=raw_text if raw_text is not None else shot_id or "missing",
        normalized_shot_id=shot_id,
        source="StyledText",
        parsed_shot_ids=parsed_shot_ids if parsed_shot_ids is not None else ([shot_id] if shot_id else []),
    )


def candidate(shot_id, path):
    return BrollCandidate(shot_id=shot_id, path=path, filename=path.rsplit("/", 1)[-1])


def test_decide_matches_marks_unparseable_guides_first():
    decisions = decide_matches([guide(None)], index={})

    assert decisions[0].status == IGNORED_NON_SHOT_TEXT
    assert decisions[0].shot_id is None
    assert decisions[0].chosen_path is None


def test_decide_matches_uses_override_before_index_candidates():
    decisions = decide_matches(
        [guide("1", raw_text="001")],
        index={"1": [candidate("1", "/broll/C001.mov")]},
        overrides={"1": "/manual/C001_override.mov"},
    )

    assert decisions[0].status == OVERRIDE
    assert decisions[0].chosen_path == "/manual/C001_override.mov"


def test_decide_matches_returns_planned_ok_for_single_candidate():
    decisions = decide_matches(
        [guide("1", raw_text="001")],
        index={"1": [candidate("1", "/broll/C001.mov")]},
    )

    assert decisions[0].status == PLANNED_OK
    assert decisions[0].chosen_path == "/broll/C001.mov"
    assert decisions[0].duplicate_candidates == ["/broll/C001.mov"]


def test_decide_matches_returns_duplicate_match_with_sorted_first_choice():
    decisions = decide_matches(
        [guide("1", raw_text="001")],
        index={
            "1": [
                candidate("1", "/broll/z_C001.mov"),
                candidate("1", "/broll/a_C001.mov"),
            ]
        },
    )

    assert decisions[0].status == DUPLICATE_MATCH
    assert decisions[0].chosen_path == "/broll/a_C001.mov"
    assert decisions[0].duplicate_candidates == ["/broll/a_C001.mov", "/broll/z_C001.mov"]


def test_decide_matches_returns_no_match_when_index_has_no_candidate():
    decisions = decide_matches([guide("009")], index={})

    assert decisions[0].status == NO_MATCH
    assert decisions[0].chosen_path is None


def test_decide_matches_marks_short_source_as_stretched_when_retime_enabled():
    decisions = decide_matches(
        [guide("1", duration=40, raw_text="001")],
        index={"1": [candidate("1", "/broll/C001.mov")]},
        source_durations={"/broll/C001.mov": 39},
        retime_short_sources=True,
    )

    assert decisions[0].status == STRETCHED
    assert decisions[0].chosen_path == "/broll/C001.mov"
    assert decisions[0].source_duration_frames == 39
    assert decisions[0].target_duration_frames == 40
    assert decisions[0].speed_percent == 97.5
    assert decisions[0].retime_method == "generated"


def test_decide_matches_marks_heavy_stretch_when_below_threshold():
    decisions = decide_matches(
        [guide("1", duration=200, raw_text="001")],
        index={"1": [candidate("1", "/broll/C001.mov")]},
        source_durations={"/broll/C001.mov": 80},
        retime_short_sources=True,
        heavy_stretch_threshold=0.5,
    )

    assert decisions[0].status == STRETCHED_HEAVY
    assert decisions[0].speed_percent == 40.0


def test_decide_matches_reports_stretch_disabled_when_retime_disabled():
    decisions = decide_matches(
        [guide("1", duration=40, raw_text="001")],
        index={"1": [candidate("1", "/broll/C001.mov")]},
        source_durations={"/broll/C001.mov": 39},
        retime_short_sources=False,
    )

    assert decisions[0].status == STRETCH_DISABLED
    assert decisions[0].chosen_path == "/broll/C001.mov"


def test_decide_matches_splits_multi_shot_guides_without_redistribution():
    decisions = decide_matches(
        [guide("888", duration=203, raw_text="888 889 数据", parsed_shot_ids=["888", "889"])],
        index={"888": [candidate("888", "/broll/C888.mov")]},
    )

    assert [decision.shot_id for decision in decisions] == ["888", "889"]
    assert [decision.status for decision in decisions] == [PLANNED_OK, NO_MATCH]
    assert [(decision.segment.segment_start, decision.segment.segment_end) for decision in decisions] == [
        (100, 202),
        (202, 303),
    ]
    assert [decision.segment.segment_duration for decision in decisions] == [102, 101]


def test_decide_matches_uses_parser_when_guides_only_have_raw_text():
    decisions = decide_matches(
        [guide(None, duration=30, raw_text="备注 5248 5249", parsed_shot_ids=[])],
        index={"5248": [candidate("5248", "/broll/C5248.MP4")]},
    )

    assert [decision.shot_id for decision in decisions] == ["5248", "5249"]
    assert [decision.status for decision in decisions] == [PLANNED_OK, NO_MATCH]
