from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass, replace
from pathlib import Path
from typing import Any

from auto_broll.config import Config
from auto_broll.core.indexer import build_index
from auto_broll.core.matcher import decide_matches
from auto_broll.core.override import parse_override_csv
from auto_broll.core.retime import generate_retimed_media, probe_video_frame_count
from auto_broll.core.verifier import verify_decisions
from auto_broll.models import (
    API_FAILED,
    DUPLICATE_MATCH,
    IGNORED_NON_SHOT_TEXT,
    NO_MATCH,
    OK,
    PLANNED_OK,
    PLACEABLE_STATUSES,
    SHORT_SOURCE,
    STRETCHED,
    STRETCHED_HEAVY,
    STRETCH_FAILED,
    STRETCH_DISABLED,
    OVERRIDE,
    MatchDecision,
    PlacementResult,
    PlannedSegment,
    ReadBackClip,
    TextPlusGuide,
    VerifyRecord,
)
from auto_broll.report.schema import RunMetadata
from auto_broll.report.writers import write_reports
from auto_broll.resolve.adapter import ResolveApiError


VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".mxf", ".avi", ".braw"}
PROBE_JSON = "probe_textplus.json"


def run_probe(config: Config) -> list[TextPlusGuide]:
    timeline = _current_timeline()
    from auto_broll.resolve.textplus import read_textplus_guides_from_timeline

    guides = read_textplus_guides_from_timeline(timeline, track_index=2, pad_width=config.shot_id_pad_width)
    _write_probe_json(config.out_dir, guides)
    return guides


def run_dry_run(config: Config, override_csv: str | None = None) -> list[VerifyRecord]:
    guides = run_probe(config)
    run_metadata = RunMetadata(mode="dry-run", timeline_name=_timeline_name_or_none())
    return run_dry_run_with_guides(guides, config, override_csv=override_csv, run_metadata=run_metadata)


def run_dry_run_with_guides(
    guides: list[TextPlusGuide],
    config: Config,
    *,
    broll_paths: list[str] | None = None,
    overrides: dict[str, str] | None = None,
    override_csv: str | None = None,
    source_durations: dict[str, int] | None = None,
    run_metadata: Any | None = None,
) -> list[VerifyRecord]:
    paths = broll_paths if broll_paths is not None else list_broll_paths(config.broll_dir)
    index = build_index(paths, config.filename_pattern, config.shot_id_pad_width)
    merged_overrides = dict(overrides or {})
    if override_csv:
        merged_overrides.update(parse_override_csv(override_csv, pad_width=config.shot_id_pad_width))
    decisions = decide_matches(
        guides,
        index,
        overrides=merged_overrides,
        source_durations=source_durations,
        allow_partial=config.allow_partial,
        retime_short_sources=config.retime_short_sources,
        heavy_stretch_threshold=config.heavy_stretch_threshold,
        retime_backend=config.retime_backend,
    )
    if source_durations is None:
        probed_durations = _probe_decision_source_durations(decisions)
        if probed_durations:
            decisions = decide_matches(
                guides,
                index,
                overrides=merged_overrides,
                source_durations=probed_durations,
                allow_partial=config.allow_partial,
                retime_short_sources=config.retime_short_sources,
                heavy_stretch_threshold=config.heavy_stretch_threshold,
                retime_backend=config.retime_backend,
            )
    verify_records = [decision_to_verify_record(decision) for decision in decisions]
    write_reports(
        config.out_dir,
        run_metadata or RunMetadata(mode="dry-run", broll_dir=config.broll_dir, out_dir=config.out_dir),
        guides,
        decisions,
        [],
        verify_records,
        v1_v2_unchanged=True,
    )
    return verify_records


def run_apply(config: Config, override_csv: str | None = None) -> list[VerifyRecord]:
    if not config.broll_dir:
        raise ValueError("--broll-dir or config.broll_dir is required for apply")

    from auto_broll.resolve.connection import connect, get_current_project, get_current_timeline
    from auto_broll.resolve.duplicate import duplicate_current_timeline
    from auto_broll.resolve.placement import (
        append_video_only_clip,
        import_media,
        media_pool_item_frame_count,
    )
    from auto_broll.resolve.textplus import read_textplus_guides_from_timeline
    from auto_broll.resolve.track import clear_auto_broll_track, ensure_auto_broll_track, locked_video_track

    resolve = connect()
    project = get_current_project(resolve)
    original = get_current_timeline(project)
    original_name = _timeline_name(original)
    duplicate = duplicate_current_timeline(project, suffix=config.duplicate_suffix)
    _set_current_timeline(project, duplicate)
    timeline_fps = _timeline_fps(duplicate)

    protected_before = protected_track_snapshot(duplicate)
    guides = read_textplus_guides_from_timeline(duplicate, track_index=2, pad_width=config.shot_id_pad_width)
    paths = list_broll_paths(config.broll_dir)
    index = build_index(paths, config.filename_pattern, config.shot_id_pad_width)
    overrides = parse_override_csv(override_csv, pad_width=config.shot_id_pad_width) if override_csv else {}
    decisions = decide_matches(
        guides,
        index,
        overrides=overrides,
        allow_partial=config.allow_partial,
        retime_short_sources=config.retime_short_sources,
        heavy_stretch_threshold=config.heavy_stretch_threshold,
        retime_backend=config.retime_backend,
    )

    media_pool = _media_pool(project)
    auto_track_index = ensure_auto_broll_track(duplicate, preferred_index=3, track_name=config.auto_broll_track_name)
    imported: dict[str, Any] = {}
    source_durations: dict[str, int] = {}
    for path in sorted({decision.chosen_path for decision in decisions if decision.chosen_path and decision.status in PLACEABLE_STATUSES}):
        media_item = import_media(media_pool, path)
        imported[path] = media_item
        frame_count = media_pool_item_frame_count(media_item)
        if frame_count is not None:
            source_durations[path] = frame_count
    if source_durations:
        decisions = decide_matches(
            guides,
            index,
            overrides=overrides,
            source_durations=source_durations,
            allow_partial=config.allow_partial,
            retime_short_sources=config.retime_short_sources,
            heavy_stretch_threshold=config.heavy_stretch_threshold,
            retime_backend=config.retime_backend,
        )
    placements: list[PlacementResult] = []
    decisions = [_materialize_retime_for_placement(decision, config, timeline_fps) for decision in decisions]
    expected_existing = [
        (_decision_start(decision), decision.generated_retime_file or decision.chosen_path)
        for decision in decisions
        if decision.status in PLACEABLE_STATUSES and (decision.generated_retime_file or decision.chosen_path)
    ]
    clear_auto_broll_track(
        duplicate,
        auto_track_index,
        expected_clips=expected_existing,
        clear_target_track=config.clear_target_track,
    )

    with locked_video_track(duplicate, 2):
        for decision in decisions:
            if decision.status not in PLACEABLE_STATUSES or not decision.chosen_path:
                placements.append(
                    PlacementResult(
                        decision.shot_id,
                        _decision_start(decision),
                        _decision_duration(decision),
                        False,
                        True,
                        decision.status,
                    )
                )
                continue
            try:
                placement_path = decision.generated_retime_file or decision.chosen_path
                media_item = imported.get(placement_path)
                if media_item is None:
                    media_item = import_media(media_pool, placement_path)
                    imported[placement_path] = media_item
                append_video_only_clip(
                    media_pool,
                    media_item,
                    record_frame=_decision_start(decision),
                    duration=_source_duration_for_timeline_placement(
                        _decision_duration(decision),
                        media_item,
                        timeline_fps,
                    ),
                    track_index=auto_track_index,
                )
                placements.append(
                    PlacementResult(
                        decision.shot_id,
                        _decision_start(decision),
                        _decision_duration(decision),
                        True,
                        True,
                        None,
                        placed_track_index=auto_track_index,
                    )
                )
            except Exception as exc:
                placements.append(
                    PlacementResult(
                        decision.shot_id,
                        _decision_start(decision),
                        _decision_duration(decision),
                        False,
                        False,
                        str(exc),
                    )
                )

    readback = read_back_clips(duplicate, auto_track_index, config.auto_broll_track_name)
    protected_after = protected_track_snapshot(duplicate)
    v1_v2_unchanged = protected_before == protected_after
    verify_records = verify_decisions(decisions, readback)
    verify_records = _merge_api_failures_from_placements(verify_records, placements)
    duplicate_name = _timeline_name(duplicate)
    write_reports(
        config.out_dir,
        RunMetadata(
            mode="apply",
            timeline_name=original_name,
            duplicate_name=duplicate_name,
            broll_dir=config.broll_dir,
            out_dir=config.out_dir,
        ),
        guides,
        decisions,
        placements,
        verify_records,
        v1_v2_unchanged=v1_v2_unchanged,
    )
    if not v1_v2_unchanged:
        raise ResolveApiError("V1/V2 protected track snapshot changed during apply")
    return verify_records


def run_verify(config: Config) -> list[VerifyRecord]:
    return run_verify_from_report(config, Path(config.out_dir) / "auto_broll_report.json")


def run_verify_from_report(config: Config, report_path: str | Path) -> list[VerifyRecord]:
    from auto_broll.resolve.connection import connect, get_current_project, get_current_timeline
    from auto_broll.resolve.track import find_video_track_by_name

    decisions = load_decisions_from_report(report_path)
    resolve = connect()
    project = get_current_project(resolve)
    timeline = get_current_timeline(project)
    track_index = find_video_track_by_name(timeline, config.auto_broll_track_name)
    if track_index is None:
        raise ResolveApiError(f"{config.auto_broll_track_name} track was not found on current timeline")

    readback = read_back_clips(timeline, track_index, config.auto_broll_track_name)
    records = verify_decisions(decisions, readback)
    write_reports(
        config.out_dir,
        RunMetadata(mode="verify", timeline_name=_timeline_name(timeline), out_dir=config.out_dir),
        [decision.guide for decision in decisions],
        decisions,
        [],
        records,
        v1_v2_unchanged=None,
    )
    return records


def run_export(config: Config, export_path: str | None = None) -> Path:
    from auto_broll.resolve.connection import connect, get_current_project, get_current_timeline

    resolve = connect()
    project = get_current_project(resolve)
    timeline = get_current_timeline(project)
    destination = Path(export_path) if export_path else Path(config.out_dir) / f"{_safe_filename(_timeline_name(timeline))}.drt"
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    ok = timeline.Export(str(destination), resolve.EXPORT_DRT, resolve.EXPORT_NONE)
    if not ok:
        raise ResolveApiError(f"timeline.Export failed: {destination}")
    return destination


def list_broll_paths(broll_dir: str) -> list[str]:
    if not broll_dir:
        raise ValueError("broll_dir is required")
    root = Path(broll_dir)
    if not root.exists():
        raise FileNotFoundError(f"B-roll folder not found: {root}")
    if root.is_file():
        return [str(root)] if root.suffix.lower() in VIDEO_EXTENSIONS else []

    paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.suffix.lower() in VIDEO_EXTENSIONS:
                paths.append(str(path))
    return paths


def decision_to_verify_record(decision: MatchDecision) -> VerifyRecord:
    if decision.status in {
        NO_MATCH,
        SHORT_SOURCE,
        DUPLICATE_MATCH,
        API_FAILED,
        IGNORED_NON_SHOT_TEXT,
        STRETCHED,
        STRETCHED_HEAVY,
        STRETCH_DISABLED,
    }:
        status = decision.status
    elif decision.status in {PLANNED_OK, OVERRIDE}:
        status = OK
    else:
        status = NO_MATCH
    return VerifyRecord(
        shot_id=decision.shot_id,
        status=status,
        intended_start=_decision_start(decision),
        actual_start=None,
        intended_duration=_decision_duration(decision),
        actual_duration=None,
        chosen_path=decision.chosen_path,
        detail=decision.note,
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
        error_message=decision.note,
    )


def load_decisions_from_report(report_path: str | Path) -> list[MatchDecision]:
    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"verification report not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    decisions: list[MatchDecision] = []
    for item in data.get("decisions", []):
        guide = TextPlusGuide(**item["guide"])
        segment_data = item.get("segment")
        if isinstance(segment_data, dict):
            segment_values = dict(segment_data)
            segment_values["guide"] = guide
            segment = PlannedSegment(**segment_values)
        else:
            segment = None
        decisions.append(
            MatchDecision(
                shot_id=item.get("shot_id"),
                guide=guide,
                chosen_path=item.get("chosen_path"),
                duplicate_candidates=list(item.get("duplicate_candidates") or []),
                status=item.get("status") or NO_MATCH,
                note=item.get("note") or "",
                source_duration=item.get("source_duration"),
                segment=segment,
                all_candidates=list(item.get("all_candidates") or item.get("duplicate_candidates") or []),
                source_duration_frames=item.get("source_duration_frames"),
                target_duration_frames=item.get("target_duration_frames"),
                speed_percent=item.get("speed_percent"),
                retime_method=item.get("retime_method") or "none",
                generated_retime_file=item.get("generated_retime_file"),
            )
        )
    return decisions


def read_back_clips(timeline, track_index: int, track_name: str) -> list[ReadBackClip]:
    items = timeline.GetItemListInTrack("video", track_index) or []
    clips: list[ReadBackClip] = []
    for item in items:
        start = int(item.GetStart())
        end = int(item.GetEnd())
        duration = int(item.GetDuration()) if hasattr(item, "GetDuration") else end - start
        name = item.GetName() if hasattr(item, "GetName") else ""
        path = _item_path(item)
        clips.append(ReadBackClip(track_name, str(name), start, end, duration, path))
    return clips


def protected_track_snapshot(timeline) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for track_index in (1, 2):
        items = timeline.GetItemListInTrack("video", track_index) or []
        for item_index, item in enumerate(items):
            start = int(item.GetStart())
            end = int(item.GetEnd())
            duration = int(item.GetDuration()) if hasattr(item, "GetDuration") else end - start
            name = str(item.GetName()) if hasattr(item, "GetName") else ""
            snapshot.append(
                {
                    "track": f"V{track_index}",
                    "item_index": item_index,
                    "name": name,
                    "start": start,
                    "end": end,
                    "duration": duration,
                }
            )
    return snapshot


def _write_probe_json(out_dir: str, guides: list[TextPlusGuide]) -> Path:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / PROBE_JSON
    path.write_text(json.dumps(_jsonable(guides), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _jsonable(value):
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _current_timeline():
    from auto_broll.resolve.connection import connect, get_current_project, get_current_timeline

    resolve = connect()
    project = get_current_project(resolve)
    return get_current_timeline(project)


def _timeline_name_or_none() -> str | None:
    try:
        return _timeline_name(_current_timeline())
    except Exception:
        return None


def _timeline_name(timeline) -> str:
    get_name = getattr(timeline, "GetName", None)
    return str(get_name()) if get_name else "Current Timeline"


def _safe_filename(name: str) -> str:
    return "".join(char if char.isalnum() or char in {" ", "_", "-"} else "_" for char in name).strip() or "timeline"


def _set_current_timeline(project, timeline) -> None:
    set_current = getattr(project, "SetCurrentTimeline", None)
    if set_current is not None:
        ok = set_current(timeline)
        if ok is False or ok is None:
            raise ResolveApiError("project.SetCurrentTimeline failed for duplicated timeline")
        current = _project_current_timeline(project)
        if _timeline_name(current) != _timeline_name(timeline):
            raise ResolveApiError(
                "project.SetCurrentTimeline current timeline mismatch "
                f"(expected={_timeline_name(timeline)}, actual={_timeline_name(current)})"
            )


def _project_current_timeline(project):
    get_current = getattr(project, "GetCurrentTimeline", None)
    if get_current is None:
        raise ResolveApiError("project.GetCurrentTimeline is unavailable after SetCurrentTimeline")
    return get_current()


def _media_pool(project):
    get_media_pool = getattr(project, "GetMediaPool", None)
    if get_media_pool is None:
        raise ResolveApiError("project.GetMediaPool is unavailable")
    media_pool = get_media_pool()
    if not media_pool:
        raise ResolveApiError("project.GetMediaPool returned no media pool")
    return media_pool


def _item_path(item) -> str | None:
    media_item = item.GetMediaPoolItem() if hasattr(item, "GetMediaPoolItem") else None
    if not media_item or not hasattr(media_item, "GetClipProperty"):
        return None
    for key in ("File Path", "FilePath", "Path"):
        try:
            value = media_item.GetClipProperty(key)
        except Exception:
            value = None
        if value:
            return str(value)
    return None


def _merge_api_failures_from_placements(records: list[VerifyRecord], placements: list[PlacementResult]) -> list[VerifyRecord]:
    failures = {(placement.shot_id, placement.intended_start): placement for placement in placements if not placement.api_ok}
    merged: list[VerifyRecord] = []
    for record in records:
        failure = failures.get((record.shot_id, record.intended_start))
        if failure:
            merged.append(
                VerifyRecord(
                    record.shot_id,
                    API_FAILED,
                    record.intended_start,
                    record.actual_start,
                    record.intended_duration,
                    record.actual_duration,
                    record.chosen_path,
                    failure.error or "placement API failed",
                )
            )
        else:
            merged.append(record)
    return merged


def _materialize_retime_for_placement(decision: MatchDecision, config: Config, timeline_fps: float) -> MatchDecision:
    if decision.status not in {STRETCHED, STRETCHED_HEAVY}:
        return decision
    if decision.generated_retime_file:
        return decision
    if decision.retime_method == "native":
        return replace(
            decision,
            status=STRETCH_FAILED,
            note="native Resolve retime is not implemented by the current scripting wrapper",
            retime_method="failed",
        )
    if not decision.chosen_path or not decision.source_duration_frames or not decision.target_duration_frames:
        return replace(
            decision,
            status=STRETCH_FAILED,
            note="missing source path or frame counts for generated retime",
            retime_method="failed",
        )

    try:
        generated = generate_retimed_media(
            decision.chosen_path,
            config.generated_retime_dir,
            decision.shot_id or "unknown",
            decision.source_duration_frames,
            decision.target_duration_frames,
            timeline_fps,
        )
    except Exception as exc:
        return replace(decision, status=STRETCH_FAILED, note=str(exc), retime_method="failed")

    return replace(decision, generated_retime_file=generated, retime_method="generated")


def _probe_decision_source_durations(decisions: list[MatchDecision]) -> dict[str, int]:
    durations: dict[str, int] = {}
    for path in sorted({decision.chosen_path for decision in decisions if decision.chosen_path}):
        frame_count = probe_video_frame_count(path)
        if frame_count is not None:
            durations[path] = frame_count
    return durations


def _decision_start(decision: MatchDecision) -> int:
    return decision.segment.segment_start if decision.segment else decision.guide.start


def _decision_end(decision: MatchDecision) -> int:
    return decision.segment.segment_end if decision.segment else decision.guide.end


def _decision_duration(decision: MatchDecision) -> int:
    return decision.segment.segment_duration if decision.segment else decision.guide.duration


def _timeline_fps(timeline) -> float:
    get_setting = getattr(timeline, "GetSetting", None)
    if get_setting is None:
        return 25.0
    value = get_setting("timelineFrameRate")
    try:
        return float(str(value).split()[0])
    except (TypeError, ValueError):
        return 25.0


def _source_duration_for_timeline_placement(target_duration: int, media_item, timeline_fps: float) -> int:
    from auto_broll.resolve.placement import media_pool_item_fps

    source_fps = media_pool_item_fps(media_item)
    if target_duration <= 0:
        return target_duration
    if not source_fps or not timeline_fps or source_fps <= 0 or timeline_fps <= 0:
        return target_duration
    return max(1, int(round(target_duration * source_fps / timeline_fps)))
