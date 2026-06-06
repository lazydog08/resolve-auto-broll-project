from __future__ import annotations

import shlex
import sys

from auto_broll import cli


def test_parser_accepts_all_modes():
    parser = cli.build_parser()

    for mode in ["doctor", "probe", "dry-run", "apply", "verify", "export"]:
        args = parser.parse_args([mode])
        assert args.mode == mode


def test_parser_accepts_timeline_drt():
    parser = cli.build_parser()

    args = parser.parse_args(["doctor", "--timeline-drt", "/project/Timeline.drt"])

    assert args.timeline_drt == "/project/Timeline.drt"


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


def test_doctor_passes_with_valid_inputs(tmp_path, capsys):
    timeline = tmp_path / "Timeline.DRT"
    timeline.write_text("resolve timeline fixture", encoding="utf-8")
    broll_dir = tmp_path / "Broll"
    broll_dir.mkdir()
    (broll_dir / "C001.mov").write_text("media fixture", encoding="utf-8")

    code = cli.main(["doctor", "--timeline-drt", str(timeline), "--broll-dir", str(broll_dir)])
    captured = capsys.readouterr()

    assert code == 0
    assert "timeline_drt" in captured.out
    assert "broll_dir" in captured.out
    assert "Import/open" in captured.out
    assert "probe" in captured.out
    assert "dry-run" in captured.out
    assert "apply" in captured.out


def test_doctor_quotes_broll_path_in_next_commands(tmp_path, capsys):
    timeline = tmp_path / "Timeline.drt"
    timeline.write_text("resolve timeline fixture", encoding="utf-8")
    broll_dir = tmp_path / "Broll folder"
    broll_dir.mkdir()
    (broll_dir / "C001.mov").write_text("media fixture", encoding="utf-8")

    code = cli.main(["doctor", "--timeline-drt", str(timeline), "--broll-dir", str(broll_dir)])
    captured = capsys.readouterr()

    assert code == 0
    assert f"--broll-dir {shlex.quote(str(broll_dir))}" in captured.out


def test_doctor_uses_configured_out_dir_in_next_commands(tmp_path, capsys):
    timeline = tmp_path / "Timeline.drt"
    timeline.write_text("resolve timeline fixture", encoding="utf-8")
    broll_dir = tmp_path / "Broll"
    broll_dir.mkdir()
    (broll_dir / "C001.mov").write_text("media fixture", encoding="utf-8")
    out_dir = tmp_path / "Reports folder"

    code = cli.main(
        [
            "doctor",
            "--timeline-drt",
            str(timeline),
            "--broll-dir",
            str(broll_dir),
            "--out-dir",
            str(out_dir),
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert f"--out-dir {shlex.quote(str(out_dir / 'probe'))}" in captured.out
    assert f"--out-dir {shlex.quote(str(out_dir / 'dry-run'))}" in captured.out
    assert f"--out-dir {shlex.quote(str(out_dir / 'apply'))}" in captured.out


def test_doctor_empty_broll_dir_returns_nonzero(tmp_path, capsys):
    timeline = tmp_path / "Timeline.drt"
    timeline.write_text("resolve timeline fixture", encoding="utf-8")
    broll_dir = tmp_path / "Broll"
    broll_dir.mkdir()

    code = cli.main(["doctor", "--timeline-drt", str(timeline), "--broll-dir", str(broll_dir)])
    captured = capsys.readouterr()

    assert code != 0
    assert "supported video files" in captured.err


def test_doctor_warns_when_video_names_have_no_shot_ids(tmp_path, capsys):
    timeline = tmp_path / "Timeline.drt"
    timeline.write_text("resolve timeline fixture", encoding="utf-8")
    broll_dir = tmp_path / "Broll"
    broll_dir.mkdir()
    (broll_dir / "interview_take.mov").write_text("media fixture", encoding="utf-8")

    code = cli.main(["doctor", "--timeline-drt", str(timeline), "--broll-dir", str(broll_dir)])
    captured = capsys.readouterr()

    assert code == 0
    assert "warning: no B-roll filenames matched" in captured.out


def test_doctor_missing_drt_returns_nonzero(tmp_path, capsys):
    broll_dir = tmp_path / "Broll"
    broll_dir.mkdir()
    (broll_dir / "C001.mov").write_text("media fixture", encoding="utf-8")

    code = cli.main(["doctor", "--broll-dir", str(broll_dir)])
    captured = capsys.readouterr()

    assert code != 0
    assert "doctor" in captured.err
    assert "timeline-drt" in captured.err


def test_doctor_wrong_suffix_returns_nonzero(tmp_path, capsys):
    timeline = tmp_path / "Timeline.txt"
    timeline.write_text("not a drt", encoding="utf-8")
    broll_dir = tmp_path / "Broll"
    broll_dir.mkdir()

    code = cli.main(["doctor", "--timeline-drt", str(timeline), "--broll-dir", str(broll_dir)])
    captured = capsys.readouterr()

    assert code != 0
    assert ".drt" in captured.err


def test_doctor_rejects_drt_directory(tmp_path, capsys):
    timeline = tmp_path / "Timeline.drt"
    timeline.mkdir()
    broll_dir = tmp_path / "Broll"
    broll_dir.mkdir()
    (broll_dir / "C001.mov").write_text("media fixture", encoding="utf-8")

    code = cli.main(["doctor", "--timeline-drt", str(timeline), "--broll-dir", str(broll_dir)])
    captured = capsys.readouterr()

    assert code != 0
    assert "must point to a file" in captured.err


def test_doctor_missing_broll_dir_returns_nonzero(tmp_path, capsys):
    timeline = tmp_path / "Timeline.drt"
    timeline.write_text("resolve timeline fixture", encoding="utf-8")

    code = cli.main(["doctor", "--timeline-drt", str(timeline), "--broll-dir", str(tmp_path / "missing")])
    captured = capsys.readouterr()

    assert code != 0
    assert "broll-dir" in captured.err


def test_doctor_does_not_import_resolve(monkeypatch, tmp_path):
    timeline = tmp_path / "Timeline.drt"
    timeline.write_text("resolve timeline fixture", encoding="utf-8")
    broll_dir = tmp_path / "Broll"
    broll_dir.mkdir()
    (broll_dir / "C001.mov").write_text("media fixture", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "DaVinciResolveScript", None)

    assert cli.main(["doctor", "--timeline-drt", str(timeline), "--broll-dir", str(broll_dir)]) == 0


def test_apply_without_broll_dir_returns_nonzero_with_clear_error(capsys):
    code = cli.main(["apply"])
    captured = capsys.readouterr()

    assert code != 0
    assert "apply" in captured.err
    assert "broll-dir" in captured.err
