from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from auto_broll.config import Config, load_config
from auto_broll.logging_setup import setup_logging
from auto_broll.resolve.adapter import ResolveApiError


ModeDispatcher = Callable[[Config, argparse.Namespace], int | None]
MODES = ("probe", "dry-run", "apply", "verify", "export")


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
    "probe": run_probe,
    "dry-run": run_dry_run,
    "apply": run_apply,
    "verify": run_verify,
    "export": run_export,
}


def _common_options_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", default=None)
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
