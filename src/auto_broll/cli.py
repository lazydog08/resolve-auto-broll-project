from __future__ import annotations

import argparse
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

from auto_broll.config import Config, load_config
from auto_broll.logging_setup import setup_logging
from auto_broll.resolve.adapter import ResolveApiError


ModeDispatcher = Callable[[Config, argparse.Namespace], int | None]
MODES = ("doctor", "probe", "dry-run", "apply", "verify", "export")


class ModeNotWiredError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-broll")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    common = _common_options_parser()

    for mode in MODES:
        subparsers.add_parser(mode, parents=[common])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    try:
        config = load_config(args.config, overrides=_config_overrides(args))
        setup_logging(config.log_level)
    except (FileNotFoundError, ValueError) as exc:
        print(f"config: {exc}", file=sys.stderr)
        return 2

    dispatcher = DISPATCHERS.get(args.mode)
    if dispatcher is None:
        print(f"{args.mode}: mode not wired", file=sys.stderr)
        return 1

    try:
        result = dispatcher(config, args)
    except ModeNotWiredError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ImportError as exc:
        print(f"{args.mode}: mode not wired ({exc})", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError, NotImplementedError, ResolveApiError) as exc:
        print(f"{args.mode}: {exc}", file=sys.stderr)
        return 1

    return int(result or 0)


def run_probe(config: Config, args: argparse.Namespace) -> int:
    from auto_broll.pipeline import run_probe as pipeline_run_probe

    guides = pipeline_run_probe(config)
    print(f"probe: wrote {len(guides)} V2 guide records to {config.out_dir}")
    return 0


def run_doctor(config: Config, args: argparse.Namespace) -> int:
    from auto_broll.core.indexer import build_index
    from auto_broll.pipeline import VIDEO_EXTENSIONS, list_broll_paths

    timeline_drt = _validated_timeline_drt(config.timeline_drt)
    broll_dir = _validated_broll_dir(config.broll_dir)
    video_paths = list_broll_paths(str(broll_dir))
    if not video_paths:
        extensions = ", ".join(sorted(VIDEO_EXTENSIONS))
        raise ValueError(
            "broll-dir contains no supported video files "
            f"({extensions})"
        )

    indexed = build_index(video_paths, config.filename_pattern, config.shot_id_pad_width)
    matched_video_count = sum(len(candidates) for candidates in indexed.values())

    print("doctor: first-run inputs look usable")
    print(f"timeline_drt: {timeline_drt}")
    print(f"broll_dir: {broll_dir}")
    print(f"video_files: {len(video_paths)}")
    print(f"files_with_shot_ids: {matched_video_count}")
    if matched_video_count == 0:
        print("warning: no B-roll filenames matched the configured A/C<digits> shot-id rule")
    print("next steps:")
    broll_arg = shlex.quote(str(broll_dir))
    probe_out_dir = shlex.quote(str(Path(config.out_dir) / "probe"))
    dry_run_out_dir = shlex.quote(str(Path(config.out_dir) / "dry-run"))
    apply_out_dir = shlex.quote(str(Path(config.out_dir) / "apply"))
    print("1. Import/open the timeline_drt file in DaVinci Resolve.")
    print("2. Make that imported timeline the current Resolve timeline.")
    print(f"3. Run: python scripts/probe_textplus.py --out-dir {probe_out_dir}")
    print(f"4. Run: python scripts/dry_run.py --broll-dir {broll_arg} --out-dir {dry_run_out_dir}")
    print(f"5. Run: python scripts/apply.py --broll-dir {broll_arg} --out-dir {apply_out_dir}")
    return 0


def run_dry_run(config: Config, args: argparse.Namespace) -> int:
    from auto_broll.pipeline import run_dry_run as pipeline_run_dry_run

    records = pipeline_run_dry_run(config, override_csv=args.override)
    print(f"dry-run: wrote {len(records)} verification rows to {config.out_dir}")
    return 0


def run_apply(config: Config, args: argparse.Namespace) -> int:
    from auto_broll.pipeline import run_apply as pipeline_run_apply

    records = pipeline_run_apply(config, override_csv=args.override)
    print(f"apply: wrote {len(records)} verification rows to {config.out_dir}")
    return 0


def run_verify(config: Config, args: argparse.Namespace) -> int:
    from auto_broll.pipeline import run_verify_from_report

    report_path = args.report or f"{config.out_dir}/auto_broll_report.json"
    records = run_verify_from_report(config, report_path)
    print(f"verify: wrote {len(records)} verification rows to {config.out_dir}")
    return 0


def run_export(config: Config, args: argparse.Namespace) -> int:
    from auto_broll.pipeline import run_export as pipeline_run_export

    path = pipeline_run_export(config, export_path=args.export_path)
    print(f"export: wrote {path}")
    return 0


DISPATCHERS: dict[str, ModeDispatcher] = {
    "doctor": run_doctor,
    "probe": run_probe,
    "dry-run": run_dry_run,
    "apply": run_apply,
    "verify": run_verify,
    "export": run_export,
}


def _common_options_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", default=None)
    parser.add_argument("--timeline-drt", dest="timeline_drt", default=None)
    parser.add_argument("--broll-dir", dest="broll_dir", default=None)
    parser.add_argument("--out-dir", dest="out_dir", default=None)
    parser.add_argument("--allow-partial", dest="allow_partial", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--retime-short-sources", dest="retime_short_sources", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--heavy-stretch-threshold", dest="heavy_stretch_threshold", type=float, default=None)
    parser.add_argument("--retime-backend", dest="retime_backend", choices=("auto", "native", "generated"), default=None)
    parser.add_argument("--generated-retime-dir", dest="generated_retime_dir", default=None)
    parser.add_argument("--clear-target-track", dest="clear_target_track", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--log-level", dest="log_level", default=None)
    parser.add_argument("--auto-broll-track-name", dest="auto_broll_track_name", default=None)
    parser.add_argument("--shot-id-pad-width", dest="shot_id_pad_width", type=int, default=None)
    parser.add_argument("--filename-pattern", dest="filename_pattern", default=None)
    parser.add_argument("--duplicate-suffix", dest="duplicate_suffix", default=None)
    parser.add_argument("--media-type", dest="media_type", type=int, default=None)
    parser.add_argument("--override", dest="override", default=None)
    parser.add_argument("--report", dest="report", default=None)
    parser.add_argument("--export-path", dest="export_path", default=None)
    return parser


def _config_overrides(args: argparse.Namespace) -> dict[str, object]:
    names = (
        "timeline_drt",
        "broll_dir",
        "out_dir",
        "allow_partial",
        "retime_short_sources",
        "heavy_stretch_threshold",
        "retime_backend",
        "generated_retime_dir",
        "clear_target_track",
        "log_level",
        "auto_broll_track_name",
        "shot_id_pad_width",
        "filename_pattern",
        "duplicate_suffix",
        "media_type",
    )
    return {name: getattr(args, name) for name in names if getattr(args, name, None) is not None}


def _validated_timeline_drt(value: str) -> Path:
    if not value:
        raise ValueError("timeline-drt is required for doctor")
    path = Path(value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"timeline-drt file not found: {path}")
    if not path.is_file():
        raise ValueError(f"timeline-drt must point to a file: {path}")
    if path.suffix.lower() != ".drt":
        raise ValueError(f"timeline-drt must point to a .drt file: {path}")
    return path


def _validated_broll_dir(value: str) -> Path:
    if not value:
        raise ValueError("broll-dir is required for doctor")
    path = Path(value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"broll-dir folder not found: {path}")
    if not path.is_dir():
        raise ValueError(f"broll-dir must point to a folder: {path}")
    return path
