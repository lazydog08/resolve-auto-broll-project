from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass
class Config:
    timeline_drt: str = ""
    broll_dir: str = ""
    auto_broll_track_name: str = "AUTO_BROLL"
    shot_id_pad_width: int = 3
    filename_pattern: str = r"(?<![A-Za-z0-9])C(\d{1,5})(?![0-9])"
    allow_partial: bool = False
    retime_short_sources: bool = True
    heavy_stretch_threshold: float = 0.5
    retime_backend: str = "auto"
    generated_retime_dir: str = "output/generated_retimes"
    clear_target_track: bool = False
    duplicate_suffix: str = "__AUTO_BROLL_v001"
    textplus_source_priority: list[str] = field(default_factory=lambda: ["StyledText", "Notes"])
    media_type: int = 1
    out_dir: str = "./reports"
    log_level: str = "INFO"


def load_config(path: str | Path | None = None, overrides: dict[str, Any] | None = None) -> Config:
    values = asdict(Config())
    config_path = DEFAULT_CONFIG_PATH if path is None else Path(path)

    if config_path.exists():
        values.update(_read_config_yaml(config_path))
    elif path is not None:
        raise FileNotFoundError(f"Config file not found: {config_path}")

    if overrides:
        values.update(_validated_overrides(overrides))

    return Config(**values)


def _read_config_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")

    _validate_keys(loaded)
    return dict(loaded)


def _validated_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    filtered = {key: value for key, value in overrides.items() if value is not None}
    _validate_keys(filtered)
    return filtered


def _validate_keys(values: dict[str, Any]) -> None:
    known = {field.name for field in fields(Config)}
    unknown = sorted(set(values) - known)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"Unknown config key: {joined}")
    backend = values.get("retime_backend")
    if backend is not None and backend not in {"auto", "native", "generated"}:
        raise ValueError("retime_backend must be one of: auto, native, generated")
