from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Sequence

from auto_broll.models import (
    API_FAILED,
    IGNORED_NON_SHOT_TEXT,
    MISSING,
    NO_MATCH,
    OK,
    PLACEABLE_STATUSES,
    SHORT_SOURCE,
    STRETCHED,
    STRETCHED_HEAVY,
    UNPARSEABLE,
    WRONG_DURATION,
    MatchDecision,
    ReadBackClip,
    VerifyRecord,
)


def verify_decisions(decisions: Sequence[MatchDecision], readback_clips: Sequence[ReadBackClip]) -> list[VerifyRecord]:
    clips_by_start: dict[int, list[ReadBackClip]] = defaultdict(list)
    for clip in readback_clips:
        clips_by_start[clip.start].append(clip)

    records: list[VerifyRecord] = []
    for decision in decisions:
        if decision.status not in PLACEABLE_STATUSES:
            records.append(_carry_non_placeable(decision))
            continue

        expected_start = _decision_start(decision)
        expected_duration = _decision_duration(decision)
        clips = clips_by_start.get(expected_start, [])
        if not clips:
            records.append(
                _record(
                    decision,
                    MISSING,
                    None,
                    f"no AUTO_BROLL clip found at frame {expected_start}",
                )
            )
            continue

        if len(clips) > 1:
            records.append(
                _record(
                    decision,
                    API_FAILED,
                    clips[0],
                    f"multiple AUTO_BROLL clips found at frame {expected_start}",
                )
            )
            continue

        clip = clips[0]
        if clip.duration != expected_duration:
            records.append(
                _record(
                    decision,
                    WRONG_DURATION,
                    clip,
                    f"duration mismatch: expected {expected_duration}, got {clip.duration}",
                )
            )
            continue

        if not _clip_matches_decision(clip, decision):
            records.append(
                _record(
                    decision,
                    API_FAILED,
                    clip,
                    f"readback clip {clip.name or clip.path or ''} does not match chosen path {decision.chosen_path}",
                )
            )
            continue

        success_status = decision.status if decision.status in {STRETCHED, STRETCHED_HEAVY} else OK
        records.append(_record(decision, success_status, clip, "readback matches segment start, duration, and shot id"))

    return records


def _carry_non_placeable(decision: MatchDecision) -> VerifyRecord:
    status = NO_MATCH if decision.status == UNPARSEABLE else decision.status
    if status == SHORT_SOURCE:
        detail = decision.note or "source is shorter than guide duration"
    elif status == NO_MATCH:
        detail = decision.note or "no matching B-roll source"
    elif status == IGNORED_NON_SHOT_TEXT:
        detail = decision.note or "annotation-only Text+ ignored"
    else:
        detail = decision.note or f"not placeable: {decision.status}"
    return _record(decision, status, None, detail)


def _record(decision: MatchDecision, status: str, clip: ReadBackClip | None, detail: str) -> VerifyRecord:
    return VerifyRecord(
        shot_id=decision.shot_id,
        status=status,
        intended_start=_decision_start(decision),
        actual_start=clip.start if clip else None,
        intended_duration=_decision_duration(decision),
        actual_duration=clip.duration if clip else None,
        chosen_path=decision.chosen_path,
        detail=detail,
        guide_index=decision.guide.item_index,
        guide_raw_text=decision.guide.raw_text,
        guide_start=decision.guide.start,
        guide_end=decision.guide.end,
        guide_duration=decision.guide.duration,
        parsed_shot_ids=list(getattr(decision.guide, "parsed_shot_ids", []) or []),
        segment_index=decision.segment.segment_index if decision.segment else 0,
        segment_count=decision.segment.segment_count if decision.segment else 1,
        segment_start=_decision_start(decision),
        segment_end=_decision_end(decision),
        segment_duration=_decision_duration(decision),
        shot_id_raw=decision.segment.shot_id_raw if decision.segment else decision.shot_id,
        shot_id_canonical=decision.segment.shot_id_canonical if decision.segment else decision.shot_id,
        matched_file=decision.chosen_path,
        all_candidates=list(decision.all_candidates or decision.duplicate_candidates),
        source_duration_frames=decision.source_duration_frames,
        target_duration_frames=decision.target_duration_frames,
        speed_percent=decision.speed_percent,
        retime_method=decision.retime_method,
        generated_retime_file=decision.generated_retime_file,
        placed_item_name=clip.name if clip else None,
        placed_start=clip.start if clip else None,
        placed_duration=clip.duration if clip else None,
        error_message=detail,
    )


def _clip_matches_decision(clip: ReadBackClip, decision: MatchDecision) -> bool:
    if not decision.chosen_path:
        return True

    expected_paths = [decision.chosen_path, decision.generated_retime_file]
    actual_path = _normalize_path(clip.path) if clip.path else None
    for path in expected_paths:
        if not path:
            continue
        expected = _normalize_path(path)
        if actual_path and actual_path == expected:
            return True

        expected_name = os.path.basename(expected)
        actual_names = [os.path.basename(value).lower() for value in [clip.path, clip.name] if value]
        if expected_name.lower() in actual_names:
            return True
    expected = _normalize_path(decision.chosen_path)
    expected_name = os.path.basename(expected)
    actual_names = [os.path.basename(value).lower() for value in [clip.path, clip.name] if value]
    return expected_name.lower() in actual_names


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _decision_start(decision: MatchDecision) -> int:
    return decision.segment.segment_start if decision.segment else decision.guide.start


def _decision_end(decision: MatchDecision) -> int:
    return decision.segment.segment_end if decision.segment else decision.guide.end


def _decision_duration(decision: MatchDecision) -> int:
    return decision.segment.segment_duration if decision.segment else decision.guide.duration
