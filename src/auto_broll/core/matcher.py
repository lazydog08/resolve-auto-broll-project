"""Decide which B-roll path, if any, should satisfy each Text+ guide."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from auto_broll.core.duration import retime_speed_percent, split_half_open_segments
from auto_broll.core.filename_parser import canonicalize_shot_id
from auto_broll.core.shot_parser import parse_shot_ids

if TYPE_CHECKING:
    from auto_broll.models import BrollCandidate, MatchDecision, TextPlusGuide


def decide_matches(
    guides: Sequence["TextPlusGuide"],
    index: Mapping[str, Sequence["BrollCandidate"]],
    overrides: Mapping[str, str] | None = None,
    source_durations: Mapping[str, int] | None = None,
    allow_partial: bool = False,
    retime_short_sources: bool = True,
    heavy_stretch_threshold: float = 0.5,
    retime_backend: str = "auto",
) -> list["MatchDecision"]:
    """Return deterministic match decisions for planned guide segments."""
    from auto_broll.models import (
        DUPLICATE_MATCH,
        IGNORED_NON_SHOT_TEXT,
        NO_MATCH,
        OVERRIDE,
        PLANNED_OK,
        STRETCHED,
        STRETCHED_HEAVY,
        STRETCH_DISABLED,
        MatchDecision,
        PlannedSegment,
    )

    overrides = {_canonical_key(key): value for key, value in (overrides or {}).items()}
    source_durations = source_durations or {}
    decisions: list[MatchDecision] = []

    for guide in guides:
        shot_ids = _guide_shot_ids(guide)
        if not shot_ids:
            segment = PlannedSegment(
                guide=guide,
                guide_index=guide.item_index,
                segment_index=0,
                segment_count=0,
                segment_start=guide.start,
                segment_end=guide.end,
                segment_duration=guide.duration,
                shot_id_raw=None,
                shot_id_canonical=None,
                ignored_non_shot_text=True,
                guide_status=IGNORED_NON_SHOT_TEXT,
            )
            decisions.append(
                MatchDecision(
                    None,
                    guide,
                    None,
                    [],
                    IGNORED_NON_SHOT_TEXT,
                    "annotation-only Text+ ignored",
                    source_duration=None,
                    segment=segment,
                    target_duration_frames=guide.duration,
                )
            )
            continue

        for segment_index, (segment_start, segment_end) in enumerate(
            split_half_open_segments(guide.start, guide.duration, len(shot_ids))
        ):
            shot_id = shot_ids[segment_index]
            segment_duration = segment_end - segment_start
            segment = PlannedSegment(
                guide=guide,
                guide_index=guide.item_index,
                segment_index=segment_index,
                segment_count=len(shot_ids),
                segment_start=segment_start,
                segment_end=segment_end,
                segment_duration=segment_duration,
                shot_id_raw=shot_id,
                shot_id_canonical=shot_id,
            )

            if shot_id in overrides:
                chosen_path = overrides[shot_id]
                status = OVERRIDE
                duplicate_candidates = [chosen_path]
                note = "manual override selected this path"
            else:
                candidate_paths = sorted(candidate.path for candidate in index.get(shot_id, []))
                if not candidate_paths:
                    decisions.append(
                        MatchDecision(
                            shot_id,
                            guide,
                            None,
                            [],
                            NO_MATCH,
                            f"no B-roll candidate found for shot id {shot_id}",
                            source_duration=None,
                            segment=segment,
                            target_duration_frames=segment_duration,
                        )
                    )
                    continue

                chosen_path = candidate_paths[0]
                duplicate_candidates = candidate_paths
                if len(candidate_paths) == 1:
                    status = PLANNED_OK
                    note = "single candidate matched this shot id"
                else:
                    status = DUPLICATE_MATCH
                    note = "multiple candidates matched; selected the first sorted path"

            source_duration = source_durations.get(chosen_path)
            speed_percent = None
            retime_method = "none"
            if source_duration is not None and source_duration < segment_duration:
                speed_percent = retime_speed_percent(source_duration, segment_duration)
                if retime_short_sources:
                    stretch_ratio = source_duration / segment_duration
                    status = STRETCHED_HEAVY if stretch_ratio < heavy_stretch_threshold else STRETCHED
                    retime_method = "native" if retime_backend == "native" else "generated"
                    note = (
                        f"source duration {source_duration} is stretched to target duration "
                        f"{segment_duration} at {speed_percent:.4f}%"
                    )
                elif allow_partial:
                    note = (
                        f"source duration {source_duration} is shorter than target duration "
                        f"{segment_duration}; partial placement allowed"
                    )
                else:
                    status = STRETCH_DISABLED
                    note = (
                        f"source duration {source_duration} is shorter than target duration "
                        f"{segment_duration}; retime_short_sources is disabled"
                    )

                decisions.append(
                    MatchDecision(
                        shot_id,
                        guide,
                        chosen_path,
                        duplicate_candidates,
                        status,
                        note,
                        source_duration=source_duration,
                        segment=segment,
                        all_candidates=duplicate_candidates,
                        source_duration_frames=source_duration,
                        target_duration_frames=segment_duration,
                        speed_percent=speed_percent,
                        retime_method=retime_method,
                    )
                )
                continue

            decisions.append(
                MatchDecision(
                    shot_id,
                    guide,
                    chosen_path,
                    duplicate_candidates,
                    status,
                    note,
                    source_duration=source_duration,
                    segment=segment,
                    all_candidates=duplicate_candidates,
                    source_duration_frames=source_duration,
                    target_duration_frames=segment_duration,
                    retime_method=retime_method,
                )
            )

    return decisions


def _guide_shot_ids(guide: "TextPlusGuide") -> list[str]:
    values = list(getattr(guide, "parsed_shot_ids", []) or [])
    if not values and getattr(guide, "raw_text", None):
        values = parse_shot_ids(guide.raw_text)
    if not values and getattr(guide, "normalized_shot_id", None):
        values = [str(guide.normalized_shot_id)]
    return [_canonical_key(value) for value in values if _canonical_key(value) is not None]


def _canonical_key(value: str | int | None) -> str | None:
    return canonicalize_shot_id(value)
