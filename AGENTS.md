# AGENTS.md

## Project Rules

This project builds a DaVinci Resolve Auto B-roll tool for 小黑. Follow `PLAN.md` before feature work.

## Execution Order

1. Keep `PLAN.md` and this `AGENTS.md` in place before feature code.
2. Build the critical-path `probe_textplus.py` first.
3. Do not proceed to Resolve placement until the probe can read V2 Text+ shot ids on the real timeline or has documented the Notes fallback.
4. Build pure logic with tests first. Those tests must run without Resolve.
5. Only `apply` may mutate Resolve, and only after duplicating the current timeline.

## Resolve Safety

- Never modify the original timeline.
- Never modify V1 or V2 clips.
- Lock V2 during placement and restore lock state.
- Place only video on `AUTO_BROLL`.
- Always pass explicit `trackIndex`.
- Check every Resolve API return value.
- Do not use GUI automation.
- Do not hand-edit `.drt` or `.drp` files.

## Test Fixture Boundary

`/Users/lazydog/Desktop/Timeline 1.drt` and the NAS B-roll folder are test fixtures only. The shipped tool must operate on the current Resolve timeline and a user-provided B-roll directory.

## Reporting

Every run should produce a JSON report, CSV report, and human-readable summary in the configured output directory. The report must make non-OK rows self-explanatory for later Claude read-only audit.

## Claude Collaboration

Codex is the executor. Claude is read-only planner/reviewer only. Before sending context to Claude, scan for credentials and private data, send the minimum needed context, and keep `.reviews/` artifacts local.
