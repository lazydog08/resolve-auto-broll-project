from __future__ import annotations

from dataclasses import dataclass, field

PLANNED_OK = "PLANNED_OK"
NO_MATCH = "NO_MATCH"
DUPLICATE_MATCH = "DUPLICATE_MATCH"
SHORT_SOURCE = "SHORT_SOURCE"
OVERRIDE = "OVERRIDE"
UNPARSEABLE = "UNPARSEABLE"
IGNORED_NON_SHOT_TEXT = "IGNORED_NON_SHOT_TEXT"
STRETCHED = "STRETCHED"
STRETCHED_HEAVY = "STRETCHED_HEAVY"
STRETCH_FAILED = "STRETCH_FAILED"
STRETCH_DISABLED = "STRETCH_DISABLED"
OFFLINE_MEDIA = "OFFLINE_MEDIA"
COLLISION = "COLLISION"

OK = "OK"
MISSING = "MISSING"
WRONG_DURATION = "WRONG_DURATION"
API_FAILED = "API_FAILED"

PLACEABLE_STATUSES = {PLANNED_OK, DUPLICATE_MATCH, OVERRIDE, STRETCHED, STRETCHED_HEAVY}
VERIFY_STATUSES = {
    OK,
    STRETCHED,
    STRETCHED_HEAVY,
    STRETCH_FAILED,
    NO_MATCH,
    IGNORED_NON_SHOT_TEXT,
    MISSING,
    OFFLINE_MEDIA,
    WRONG_DURATION,
    COLLISION,
    API_FAILED,
}


@dataclass(frozen=True)
class TextPlusGuide:
    track: str
    item_index: int
    name: str
    start: int
    end: int
    duration: int
    raw_text: str
    normalized_shot_id: str | None
    source: str
    parsed_shot_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BrollCandidate:
    shot_id: str
    path: str
    filename: str
    shot_id_raw: str = ""
    shot_id_canonical: str = ""


@dataclass(frozen=True)
class PlannedSegment:
    guide: TextPlusGuide
    guide_index: int
    segment_index: int
    segment_count: int
    segment_start: int
    segment_end: int
    segment_duration: int
    shot_id_raw: str | None
    shot_id_canonical: str | None
    ignored_non_shot_text: bool = False
    guide_status: str = ""


@dataclass(frozen=True)
class MatchDecision:
    shot_id: str | None
    guide: TextPlusGuide
    chosen_path: str | None
    duplicate_candidates: list[str] = field(default_factory=list)
    status: str = NO_MATCH
    note: str = ""
    source_duration: int | None = None
    segment: PlannedSegment | None = None
    all_candidates: list[str] = field(default_factory=list)
    source_duration_frames: int | None = None
    target_duration_frames: int | None = None
    speed_percent: float | None = None
    retime_method: str = "none"
    generated_retime_file: str | None = None

    def __post_init__(self) -> None:
        if self.all_candidates:
            candidates = list(self.all_candidates)
        else:
            candidates = list(self.duplicate_candidates)
            object.__setattr__(self, "all_candidates", candidates)
        if not self.duplicate_candidates and candidates:
            object.__setattr__(self, "duplicate_candidates", candidates)
        if self.source_duration_frames is None and self.source_duration is not None:
            object.__setattr__(self, "source_duration_frames", self.source_duration)
        if self.source_duration is None and self.source_duration_frames is not None:
            object.__setattr__(self, "source_duration", self.source_duration_frames)
        if self.target_duration_frames is None:
            segment_duration = self.segment.segment_duration if self.segment else self.guide.duration
            object.__setattr__(self, "target_duration_frames", segment_duration)


@dataclass(frozen=True)
class PlacementResult:
    shot_id: str | None
    intended_start: int
    intended_duration: int
    placed: bool
    api_ok: bool
    error: str | None
    placed_track_index: int | None = None
    placed_item_name: str | None = None
    placed_start: int | None = None
    placed_duration: int | None = None


@dataclass(frozen=True)
class ReadBackClip:
    track: str
    name: str
    start: int
    end: int
    duration: int
    path: str | None


@dataclass(frozen=True)
class VerifyRecord:
    shot_id: str | None
    status: str
    intended_start: int
    actual_start: int | None
    intended_duration: int
    actual_duration: int | None
    chosen_path: str | None
    detail: str
    guide_index: int | None = None
    guide_raw_text: str = ""
    guide_start: int | None = None
    guide_end: int | None = None
    guide_duration: int | None = None
    parsed_shot_ids: list[str] = field(default_factory=list)
    segment_index: int | None = None
    segment_count: int | None = None
    segment_start: int | None = None
    segment_end: int | None = None
    segment_duration: int | None = None
    shot_id_raw: str | None = None
    shot_id_canonical: str | None = None
    matched_file: str | None = None
    all_candidates: list[str] = field(default_factory=list)
    source_duration_frames: int | None = None
    target_duration_frames: int | None = None
    speed_percent: float | None = None
    retime_method: str = "none"
    generated_retime_file: str | None = None
    placed_track_index: int | None = None
    placed_item_name: str | None = None
    placed_start: int | None = None
    placed_duration: int | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.guide_start is None:
            object.__setattr__(self, "guide_start", self.intended_start)
        if self.guide_duration is None:
            object.__setattr__(self, "guide_duration", self.intended_duration)
        if self.segment_start is None:
            object.__setattr__(self, "segment_start", self.intended_start)
        if self.segment_duration is None:
            object.__setattr__(self, "segment_duration", self.intended_duration)
        if self.placed_start is None:
            object.__setattr__(self, "placed_start", self.actual_start)
        if self.placed_duration is None:
            object.__setattr__(self, "placed_duration", self.actual_duration)
        if self.matched_file is None:
            object.__setattr__(self, "matched_file", self.chosen_path)
        if self.error_message is None:
            object.__setattr__(self, "error_message", self.detail)
