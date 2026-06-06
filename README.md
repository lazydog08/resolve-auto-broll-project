# Auto B-roll for DaVinci Resolve

This project helps a Codex user place B-roll safely in DaVinci Resolve. It reads shot ids from Text+ clips on V2 of the current Resolve timeline, matches them to B-roll files in a user-provided folder, and places video-only clips on a duplicated timeline track named `AUTO_BROLL`.

## First Run With Codex

Give Codex two paths before asking it to run the tool:

- `timeline_drt`: a `.drt` timeline file that follows the project rules below.
- `broll_dir`: a folder containing B-roll videos named with explicit `C<digits>` shot ids, such as `C001.mov`, `20260605_C888.mp4`, or `C0888.MP4`.

Example instruction to Codex:

```text
Use this Auto B-roll project. My timeline_drt is /path/to/Timeline.drt and my broll_dir is /path/to/Broll. Run doctor first, then tell me the next Resolve steps.
```

Install and run the first preflight:

```bash
git clone https://github.com/lazydog08/resolve-auto-broll-project.git
cd resolve-auto-broll-project
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
cp config.example.yaml config.yaml
python scripts/doctor.py --timeline-drt "/path/to/Timeline.drt" --broll-dir "/path/to/Broll"
```

`doctor` does not require Resolve. It only checks that the `.drt` file exists, the B-roll folder exists, video files are present, and filenames can be matched by the configured shot-id rule.

## Timeline And B-roll Rules

The `.drt` timeline must be imported/opened in DaVinci Resolve before Resolve-dependent commands run. The tool does not parse or edit `.drt` files directly.

The timeline should have:

- V2 Text+ guide clips containing shot ids such as `888`, `C888`, `C0888`, `shot 888`, `clip 888`, or `镜头888`.
- V1 and V2 reserved for the original edit and guide layer. The tool never edits these tracks.
- Room for a generated video-only track named `AUTO_BROLL`.

The B-roll folder should contain video files with explicit `C<digits>` tokens in the filename. Filename matching intentionally ignores arbitrary dates, camera card numbers, and take numbers unless they are part of a `C<digits>` token.

## Resolve Setup

DaVinci Resolve Studio must be running with the target project and imported timeline open.

In Resolve preferences, enable:

```text
System -> General -> External scripting using: Local
```

Typical macOS environment values:

```bash
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules"
```

After `doctor` passes:

```bash
python scripts/probe_textplus.py --out-dir reports/probe
python scripts/dry_run.py --broll-dir "/path/to/Broll" --out-dir reports/dry-run
python scripts/apply.py --broll-dir "/path/to/Broll" --out-dir reports/apply
python scripts/verify.py --out-dir reports/verify --report reports/apply/auto_broll_report.json
python scripts/export.py --out-dir reports/export --export-path reports/export/Timeline_AUTO_BROLL.drt
```

`apply` duplicates the current Resolve timeline before placement. The original timeline is not modified.

## Local Config

Create local config on each Mac:

```bash
cp config.example.yaml config.yaml
```

Fill these local values first:

- `timeline_drt`: the `.drt` file you import/open in Resolve. This is a preflight reference only.
- `broll_dir`: the B-roll folder path for this Mac.
- `out_dir`: report output folder, usually `./reports` or an absolute local path.
- `generated_retime_dir`: generated retime clip output folder.

CLI flags override `config.yaml`, so these are equivalent:

```bash
python scripts/doctor.py --timeline-drt "/path/to/Timeline.drt" --broll-dir "/path/to/Broll"
python scripts/doctor.py --config config.yaml
```

## Safety

- `doctor`, `probe`, and `dry-run` make no timeline changes.
- `apply` duplicates the current timeline before placement.
- V1 and V2 are protected tracks.
- V2 is locked during placement and its lock state is restored.
- B-roll is placed only as video on `AUTO_BROLL`.
- The tool uses Resolve scripting only. It does not automate the GUI or edit `.drt` / `.drp` files.

## Reports

Every run writes reports to the configured output directory:

- `auto_broll_report.json`
- `auto_broll_report.csv`
- `auto_broll_summary.txt`

Non-OK rows are written with enough detail for later review.

## Tests

Pure tests run without Resolve:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src tests scripts
```

## Repository Hygiene

`config.yaml`, `.reviews/`, `reports/`, `output/`, Resolve exports, media files, caches, logs, and virtual environments are local-only and intentionally ignored by Git.
