from auto_broll.models import (
    API_FAILED,
    DUPLICATE_MATCH,
    MISSING,
    NO_MATCH,
    OK,
    PLANNED_OK,
    SHORT_SOURCE,
    UNPARSEABLE,
    WRONG_DURATION,
    BrollCandidate,
    MatchDecision,
    PlacementResult,
    ReadBackClip,
    TextPlusGuide,
    VerifyRecord,
)


def test_textplus_guide_stores_exclusive_duration_contract():
    guide = TextPlusGuide(
        track="V2",
        item_index=3,
        name="Text+ 001",
        start=100,
        end=160,
        duration=60,
        raw_text="镜头001",
        normalized_shot_id="001",
        source="StyledText",
    )

    assert guide.duration == guide.end - guide.start
    assert guide.normalized_shot_id == "001"


def test_matching_and_verification_status_constants_are_stable():
    assert PLANNED_OK == "PLANNED_OK"
    assert UNPARSEABLE == "UNPARSEABLE"
    assert {OK, MISSING, NO_MATCH, DUPLICATE_MATCH, SHORT_SOURCE, WRONG_DURATION, API_FAILED} == {
        "OK",
        "MISSING",
        "NO_MATCH",
        "DUPLICATE_MATCH",
        "SHORT_SOURCE",
        "WRONG_DURATION",
        "API_FAILED",
    }


def test_report_dataclasses_have_expected_fields():
    guide = TextPlusGuide("V2", 0, "Text+ 001", 10, 20, 10, "001", "001", "StyledText")
    candidate = BrollCandidate("001", "/broll/C001.mov", "C001.mov")
    decision = MatchDecision("001", guide, candidate.path, [candidate.path], PLANNED_OK, "single match")
    placement = PlacementResult("001", 10, 10, True, True, None)
    readback = ReadBackClip("AUTO_BROLL", "C001.mov", 10, 20, 10, candidate.path)
    verify = VerifyRecord("001", OK, 10, 10, 10, 10, candidate.path, "matched")

    assert decision.guide is guide
    assert placement.api_ok is True
    assert readback.duration == 10
    assert verify.status == OK
