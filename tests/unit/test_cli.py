from __future__ import annotations

from auto_broll import cli


def test_parser_accepts_all_modes():
    parser = cli.build_parser()

    for mode in ["probe", "dry-run", "apply", "verify", "export"]:
        args = parser.parse_args([mode])
        assert args.mode == mode


def test_parser_accepts_verify_and_export_paths():
    parser = cli.build_parser()

    verify_args = parser.parse_args(["verify", "--report", "reports/apply/auto_broll_report.json"])
    export_args = parser.parse_args(["export", "--export-path", "reports/out.drt"])

    assert verify_args.report == "reports/apply/auto_broll_report.json"
    assert export_args.export_path == "reports/out.drt"


def test_cli_passes_loaded_config_to_dispatcher(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "broll_dir: /from/yaml",
                "out_dir: /from/yaml/reports",
                "allow_partial: false",
                "log_level: INFO",
            ]
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_dispatch(config, args):
        calls.append((config, args))
        return 7

    monkeypatch.setattr(cli, "DISPATCHERS", {"dry-run": fake_dispatch})

    code = cli.main(
        [
            "dry-run",
            "--config",
            str(config_path),
            "--broll-dir",
            "/from/cli",
            "--out-dir",
            "/from/cli/reports",
            "--allow-partial",
            "--log-level",
            "DEBUG",
        ]
    )

    assert code == 7
    assert len(calls) == 1
    config, args = calls[0]
    assert config.broll_dir == "/from/cli"
    assert config.out_dir == "/from/cli/reports"
    assert config.allow_partial is True
    assert config.log_level == "DEBUG"
    assert args.mode == "dry-run"


def test_apply_without_broll_dir_returns_nonzero_with_clear_error(capsys):
    code = cli.main(["apply"])
    captured = capsys.readouterr()

    assert code != 0
    assert "apply" in captured.err
    assert "broll-dir" in captured.err
