# Auto B-roll for DaVinci Resolve

This tool reads shot ids from Text+ clips on V2 of the current Resolve timeline, matches them to B-roll files in a provided folder, and places matching video-only clips on a duplicated timeline track named `AUTO_BROLL`.

## Safety

- `dry-run` makes no timeline changes.
- `apply` duplicates the current timeline before placement.
- V1 and V2 are treated as protected tracks.
- The tool uses Resolve scripting only. It does not automate the GUI or edit `.drt` files.

## macOS Resolve Scripting Setup

DaVinci Resolve Studio must be running with the target project and timeline open.

In Resolve preferences, enable:

`System -> General -> External scripting using: Local`

Typical environment values:

```bash
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules"
```

## Commands

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Create local config on each Mac:

```bash
cp config.example.yaml config.yaml
```

Fill or override these local values:

- `broll_dir`: B-roll folder path for this Mac.
- `out_dir`: report output folder, usually `./reports` or an absolute local path.
- `generated_retime_dir`: generated retime clip output folder.

Open or import the `.drp` / `.drt` test material in DaVinci Resolve, then make the target timeline current before running Resolve-dependent commands. The tool operates on the current Resolve timeline; it does not parse `.drp` or `.drt` files directly.

Probe the current timeline:

```bash
python scripts/probe_textplus.py --out-dir reports
```

Dry run with a B-roll folder:

```bash
python scripts/dry_run.py --broll-dir "/Volumes/path/to/2_Broll" --out-dir reports
```

Apply on a duplicate timeline:

```bash
python scripts/apply.py --broll-dir "/Volumes/path/to/2_Broll" --out-dir reports
```

Verify an existing result:

```bash
python scripts/verify.py --out-dir reports
```

## Test Fixture Note

The current local test timeline file is `/Users/lazydog/Desktop/Timeline 1.drt`. The tool does not parse that file directly; open/import it in Resolve and make it the current timeline before running Resolve-dependent scripts.

## Repository Hygiene

`config.yaml`, `.reviews/`, `reports/`, `output/`, Resolve exports, media files, caches, logs, and virtual environments are local-only and intentionally ignored by Git.
