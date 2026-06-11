from __future__ import annotations

from dataclasses import asdict

import pytest

from auto_broll.config import Config, load_config


def test_example_config_matches_project_defaults():
    config = load_config("config.example.yaml")

    assert asdict(config) == {
        "timeline_drt": "",
        "broll_dir": "",
        "auto_broll_track_name": "AUTO_BROLL",
        "shot_id_pad_width": 3,
        "filename_pattern": r"(?<![A-Za-z0-9])(?:A|C)(\d{1,5})(?![0-9])",
        "allow_partial": False,
        "retime_short_sources": True,
        "heavy_stretch_threshold": 0.5,
        "retime_backend": "auto",
        "generated_retime_dir": "output/generated_retimes",
        "clear_target_track": False,
        "duplicate_suffix": "__AUTO_BROLL_v001",
        "textplus_source_priority": ["StyledText", "Notes"],
        "media_type": 1,
        "out_dir": "./reports",
        "log_level": "INFO",
    }


def test_load_config_layers_yaml_then_cli_overrides(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n".join(
            [
                "broll_dir: /from/yaml",
                "timeline_drt: /from/yaml/Timeline.drt",
                "out_dir: /reports/yaml",
                "allow_partial: false",
                "retime_short_sources: false",
                "heavy_stretch_threshold: 0.75",
                "log_level: WARNING",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(
        path,
        overrides={
            "broll_dir": "/from/cli",
            "out_dir": None,
            "allow_partial": True,
            "retime_short_sources": True,
            "log_level": "DEBUG",
        },
    )

    assert config.broll_dir == "/from/cli"
    assert config.timeline_drt == "/from/yaml/Timeline.drt"
    assert config.out_dir == "/reports/yaml"
    assert config.allow_partial is True
    assert config.retime_short_sources is True
    assert config.heavy_stretch_threshold == 0.75
    assert config.log_level == "DEBUG"
    assert config.auto_broll_track_name == "AUTO_BROLL"


def test_load_config_without_default_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert load_config() == Config()


def test_load_config_rejects_unknown_keys(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("unexpected: value\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown config key"):
        load_config(path)
