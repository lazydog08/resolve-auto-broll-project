# DaVinci Resolve Auto B-roll Tool Plan

## Goal

Build a Python tool for macOS + DaVinci Resolve Studio that reads shot ids from Text+ clips on V2 of the current timeline, matches each guide to a B-roll file from a user-provided folder, places video-only B-roll on a duplicate timeline track named `AUTO_BROLL`, and writes a verification report proving the result.

This project is not tied to the current test fixture. `/Users/lazydog/Desktop/Timeline 1.drt` and the NAS B-roll folder are only test material.

## v2.2 Incremental Update

This update changes the planning grain from one guide -> one placement to one guide -> zero or more planned segments. A Text+ guide is now a tag string: it may contain one shot id, multiple shot ids, shot ids plus notes, or only annotation text. Only recognized shot-id tokens drive B-roll placement.

New behavior:

- Parse Text+ into an ordered list of raw shot ids.
- Ignore annotation-only guides such as `数据`, `动效`, `备注`, `animation`, and similar non-shot notes. Report them as `IGNORED_NON_SHOT_TEXT`, not `NO_MATCH`.
- Split a multi-shot Text+ guide into equal half-open frame segments. The first remainder segments receive one extra frame.
- Match by canonical numeric id, so `888`, `C888`, and `C0888` compare as the same id. Filename matching remains anchored to explicit `C<digits>` tokens.
- If a source clip is shorter than the target segment, slow it uniformly to fill the segment exactly when retiming is enabled. Report `STRETCHED`, `STRETCHED_HEAVY`, or `STRETCH_FAILED`; do not silently skip as `SHORT_SOURCE`.
- `apply` must be safe to re-run: the duplicated timeline should contain one clean generated AUTO_BROLL result, not stacked duplicate layers.

## Non-Negotiable Rules

- Never modify the original timeline. `apply` must first duplicate the current timeline as `<original>__AUTO_BROLL_v001`, incrementing the version if needed.
- Never modify, move, retime, delete, or overwrite V1 or V2 clips.
- Lock V2 during placement and restore the lock state afterward.
- Place B-roll only on a video track named `AUTO_BROLL`, defaulting to V3 when created.
- Always pass `trackIndex` explicitly.
- Video only: `mediaType = 1`; never place B-roll audio.
- Do not ripple, do not overwrite non-`AUTO_BROLL` clips.
- If the source is shorter than the target segment, retime/stretch uniformly when `retime_short_sources` is enabled. Never report success unless the read-back placed duration equals the target segment duration.
- Check every Resolve API return value. `None` and `False` are errors unless documented as allowed.
- Use the Resolve Python scripting API only. Do not automate the GUI and do not hand-edit `.drt` or `.drp` files.

## Module Breakdown

### `auto_broll.models`

Pure dataclasses and status constants shared by all modules.

Contracts:

- `TextPlusGuide(track: str, item_index: int, name: str, start: int, end: int, duration: int, raw_text: str, parsed_shot_ids: list[str], normalized_shot_id: str | None, source: str)`
- `BrollCandidate(shot_id: str, path: str, filename: str, shot_id_raw: str, shot_id_canonical: str)`
- `PlannedSegment(guide: TextPlusGuide, guide_index: int, segment_index: int, segment_count: int, segment_start: int, segment_end: int, segment_duration: int, shot_id_raw: str | None, shot_id_canonical: str | None, ignored_non_shot_text: bool = False, guide_status: str = "")`
- `MatchDecision(segment: PlannedSegment, chosen_path: str | None, all_candidates: list[str], status: str, note: str, source_duration_frames: int | None = None, target_duration_frames: int | None = None, speed_percent: float | None = None, retime_method: str = "none", generated_retime_file: str | None = None)`
- `PlacementResult(shot_id: str | None, intended_start: int, intended_duration: int, placed: bool, api_ok: bool, error: str | None, placed_track_index: int | None = None, placed_item_name: str | None = None, placed_start: int | None = None, placed_duration: int | None = None)`
- `ReadBackClip(track: str, name: str, start: int, end: int, duration: int, path: str | None)`
- `VerifyRecord(guide_index: int, guide_raw_text: str, guide_start: int, guide_end: int, guide_duration: int, parsed_shot_ids: list[str], segment_index: int | None, segment_count: int, segment_start: int, segment_end: int, segment_duration: int, shot_id_raw: str | None, shot_id_canonical: str | None, matched_file: str | None, all_candidates: list[str], source_duration_frames: int | None, target_duration_frames: int | None, speed_percent: float | None, retime_method: str, generated_retime_file: str | None, placed_track_index: int | None, placed_item_name: str | None, placed_start: int | None, placed_duration: int | None, status: str, error_message: str | None)`

Status values:

- Planning/matching: `PLANNED_OK`, `NO_MATCH`, `DUPLICATE_MATCH`, `SHORT_SOURCE`, `OVERRIDE`, `UNPARSEABLE`, `IGNORED_NON_SHOT_TEXT`, `STRETCHED`, `STRETCHED_HEAVY`, `STRETCH_FAILED`, `STRETCH_DISABLED`, `COLLISION`
- Verification: `OK`, `STRETCHED`, `STRETCHED_HEAVY`, `STRETCH_FAILED`, `NO_MATCH`, `IGNORED_NON_SHOT_TEXT`, `MISSING`, `OFFLINE_MEDIA`, `WRONG_DURATION`, `COLLISION`, `API_FAILED`

### `auto_broll.core.shot_parser`

Inputs:

- `raw_text: str`
- `pad_width: int = 3`

Output:

- Ordered list of raw numeric shot ids, such as `["888", "889"]`.

Rules:

- Accept bare numeric shot tokens of 3 to 5 digits when separated by whitespace, punctuation, slash, brackets, or string boundaries.
- Accept `C888`, `C0888`, `shot 888`, `clip 888`, `镜头888`.
- Preserve order.
- Ignore non-shot words such as `数据`, `动效`, `备注`, `animation`, `motion graphics`, `chart`, and similar annotation text.
- Reject digits embedded in normal words, including `数据2026`, `图表01`, `5248A`, `A5248`, `1080p`, `50%`, and `v2`.
- Return an empty list when no valid shot id exists.

### `auto_broll.core.filename_parser`

Inputs:

- `filename: str`
- `pattern: str`
- `pad_width: int`

Output:

- Canonical numeric shot id with insignificant leading zeros removed, or `None`.

Rules:

- Anchor only on explicit `C<digits>` tokens.
- Do not match arbitrary dates, card ids, camera ids, or take numbers.
- Preserve raw and canonical ids in candidates.

### `auto_broll.core.indexer`

Inputs:

- `paths: Iterable[str]`
- filename parser settings.

Output:

- `dict[str, list[BrollCandidate]]`, grouped by shot id.

### `auto_broll.core.override`

Inputs:

- override CSV path with columns `shot_id,path`.

Output:

- `dict[str, str]`.

Rules:

- Normalize shot ids using the same pad width.
- Reject malformed rows.

### `auto_broll.core.matcher`

Inputs:

- `guides: list[TextPlusGuide]`
- `index: dict[str, list[BrollCandidate]]`
- `overrides: dict[str, str]`
- optional `source_durations: dict[str, int]`
- `allow_partial: bool`

Output:

- `list[MatchDecision]`.

Rules:

- Annotation-only guides become `IGNORED_NON_SHOT_TEXT`.
- Guides with multiple shot ids produce multiple planned segments.
- Override path wins when present.
- One candidate becomes `PLANNED_OK`.
- Multiple candidates become `DUPLICATE_MATCH`, sorted first chosen deterministically and all candidates listed.
- No candidate becomes `NO_MATCH`.
- Source shorter than segment duration becomes `STRETCHED` or `STRETCHED_HEAVY` when retiming is enabled, otherwise `STRETCH_DISABLED` or `SHORT_SOURCE`.

### `auto_broll.core.verifier`

Inputs:

- `decisions: list[MatchDecision]`
- `readback_clips: list[ReadBackClip]`

Output:

- `list[VerifyRecord]`.

Rules:

- Non-placeable statuses carry through.
- Ignored annotation guides require zero placement and are not failures.
- Placeable decisions must produce exactly one read-back clip at the same segment start.
- Duration must match the segment exactly.
- Multi-shot slices must have no gap, overlap, or drift.
- Wrong/missing/duplicate read-back state is explicit in the report.

### `auto_broll.core.duration`

Centralizes frame math. The project treats Resolve item end frames as exclusive, so `duration = end - start`. The probe must confirm this on the live test timeline.

Also provides:

- Equal segment splitting over half-open guide intervals.
- Retime speed math: `speed_percent = source_frames / target_frames * 100`.
- Heavy stretch detection using `heavy_stretch_threshold`.

### `auto_broll.config`

Loads `config.yaml` and CLI overrides into a typed `Config`.

New config keys:

- `timeline_drt: ""` as a first-run preflight reference to the `.drt` file the user imports into Resolve. The tool never parses or edits this file.
- `retime_short_sources: true`
- `heavy_stretch_threshold: 0.5`
- `retime_backend: "auto"` with allowed values `auto`, `native`, `generated`
- `generated_retime_dir: output/generated_retimes`
- `clear_target_track: false`

### `auto_broll.report.writers`

Writes:

- `auto_broll_report.json`
- `auto_broll_report.csv`
- `auto_broll_summary.txt`

### `auto_broll.resolve`

The only package allowed to import `DaVinciResolveScript`.

Modules:

- `connection.py`: locate Resolve module, connect, get current project/timeline.
- `adapter.py`: typed wrapper around risky Resolve calls.
- `textplus.py`: read V2 TimelineItems, enter Fusion comp, read Text+/TextPlus `StyledText`, fallback to Notes.
- `duplicate.py`: duplicate timeline with unique suffix.
- `track.py`: ensure `AUTO_BROLL`, track naming, V2 lock/restore.
- `placement.py`: import media and append video-only clipInfo with explicit `trackIndex`.
- `retime.py` if needed: native retime probe and generated-media fallback helpers.

Local Resolve finding:

- The v2.2 prompt warned that AppendToTimeline source `endFrame` is usually inclusive. A live apply/readback on this Mac showed that using `endFrame = source_start + duration - 1` made every placed clip one frame short. The wrapper therefore uses `endFrame = source_start + duration` and relies on read-back verification to catch any future API drift.

Every Resolve wrapper either returns a typed value or raises `ResolveApiError`.

### `auto_broll.cli`

Modes:

- `doctor`: validate the user-provided `.drt` timeline path and B-roll folder path without connecting to Resolve, then print the import/probe/dry-run/apply next steps.
- `probe`: read V2 guides and write JSON; no timeline changes.
- `dry-run`: probe, index, match, write would-place report; no timeline changes.
- `apply`: duplicate timeline, create/use `AUTO_BROLL`, place B-roll, verify, report.
- `verify`: verify an existing `AUTO_BROLL` result.
- `export`: export duplicated timeline/report artifacts where supported.

## Critical-Path Gate

Before parallel implementation beyond pure logic integration, `scripts/probe_textplus.py` must run on the real Resolve timeline and emit JSON records:

```json
{
  "track": "V2",
  "item_index": 0,
  "start": 120,
  "end": 210,
  "duration": 90,
  "raw_text": "镜头001",
  "parsed_shot_ids": ["001"],
  "normalized_shot_id": "001",
  "source": "StyledText"
}
```

Gate pass criteria:

- Every V2 Text+ guide item appears in the output.
- `duration == end - start` and duration is positive.
- Expected guide items have non-empty `raw_text`.
- Expected guide items parse to non-empty `parsed_shot_ids`.

Fallback rule:

- Try `StyledText` first.
- If a guide item cannot provide readable StyledText, try the item Notes property.
- If Notes is used, record `source = "Notes"` and log a warning.
- If both fail, keep the item in the report with an empty `parsed_shot_ids` list; do not guess.

## Parallelization Map

After the probe gate decides the read strategy:

- Stream A: pure logic modules and tests: parser, filename parser, indexer, override, matcher, verifier, duration.
- Stream B: Resolve boundary: connection, adapter, Text+ reader, duplicate timeline, track management, placement.
- Stream C: reports: JSON, CSV, human summary.
- Stream D: CLI/config/logging integration.

Streams A and C do not need Resolve. Stream B needs Resolve. Stream D integrates the frozen contracts.

## Testing Plan

Unit tests must pass without Resolve:

- `test_shot_parser.py`: accepted forms, multiple shot ids, annotation-only text, embedded-number rejection, ordered output.
- `test_filename_parser.py`: explicit `C<digits>` match; reject dates/card/camera/take-only numbers.
- `test_indexer.py`: recursive file grouping, duplicate candidates, unsupported names ignored.
- `test_override.py`: CSV parsing, normalized ids, malformed rows.
- `test_matcher.py`: planned OK, duplicate, no match, override wins, annotation ignored, multi-shot segments, short source stretch/disabled statuses.
- `test_verifier.py`: OK, stretched OK, missing, duplicate placed clips, wrong duration, carried statuses, annotation ignored, multi-shot missing slice.
- `test_duration.py`: end-exclusive duration and invalid frame ranges.

Integration tests are opt-in and skipped unless Resolve is available.

## Acceptance Checklist

- `PLAN.md` and `AGENTS.md` exist before feature code.
- `probe_textplus.py` can read V2 Text+ shot ids on the test timeline or explicitly documents the Notes fallback.
- `dry-run` produces reports and zero timeline changes.
- `apply` works only on a duplicate timeline.
- Matched segments each get exactly one `AUTO_BROLL` clip with identical start and duration.
- V1 and V2 snapshots are identical before and after `apply`.
- Text+ guides without a matching B-roll are reported and do not crash the run.
- Annotation-only Text+ guides are reported as ignored and do not require B-roll placement.
- Short source clips are stretched or explicitly reported as stretch failures; they are not silently skipped as OK.
- Report statuses match the actual read-back timeline state.
- Unit tests for pure logic pass without Resolve.

## Current Fixture Notes

- Test timeline files found locally: `/Users/lazydog/Desktop/Timeline 1.drt` and `/Volumes/6_临时文件夹/Timeline 2.drt`.
- The tool will use the current open Resolve timeline, not directly parse or edit the `.drt`.
- Test B-roll folder is expected from NAS; this path is a fixture only and must stay configurable.
