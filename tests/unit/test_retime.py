from pathlib import Path
from types import SimpleNamespace

import pytest

from auto_broll.core.retime import (
    build_ffmpeg_retime_command,
    generated_retime_path,
    generate_retimed_media,
    probe_video_frame_count,
)


def test_generated_retime_path_is_deterministic_and_includes_target_shape(tmp_path):
    source = tmp_path / "C0896.MP4"
    source.write_text("fixture")

    first = generated_retime_path(source, tmp_path / "retimes", "896", 195, 202, 25.0)
    second = generated_retime_path(source, tmp_path / "retimes", "896", 195, 202, 25.0)

    assert first == second
    assert first.parent == tmp_path / "retimes"
    assert "shot896" in first.name
    assert "195to202" in first.name
    assert first.suffix == ".mp4"


def test_build_ffmpeg_retime_command_is_video_only_and_exact_frame_bounded(tmp_path):
    source = tmp_path / "C0896.MP4"
    output = tmp_path / "retimed.mp4"

    command = build_ffmpeg_retime_command(source, output, source_frames=195, target_frames=202, timeline_fps=25.0)

    assert command[0] == "ffmpeg"
    assert "-an" in command
    filter_arg = command[command.index("-vf") + 1]
    assert "setpts=1.03589743589743" in filter_arg
    assert "trim=start_frame=0:end_frame=202" in filter_arg
    assert command[-1] == str(output)


def test_generate_retimed_media_uses_cache_when_frame_count_matches(tmp_path, monkeypatch):
    source = tmp_path / "C0896.MP4"
    source.write_text("fixture")
    output_dir = tmp_path / "retimes"
    cached = generated_retime_path(source, output_dir, "896", 195, 202, 25.0)
    cached.parent.mkdir(parents=True)
    cached.write_text("cached")

    monkeypatch.setattr("auto_broll.core.retime.probe_video_frame_count", lambda path: 202)

    assert generate_retimed_media(source, output_dir, "896", 195, 202, 25.0) == str(cached)


def test_generate_retimed_media_raises_when_ffmpeg_output_has_wrong_frame_count(tmp_path, monkeypatch):
    source = tmp_path / "C0896.MP4"
    source.write_text("fixture")

    def fake_run(command, check, capture_output, text):
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("generated")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("auto_broll.core.retime.subprocess.run", fake_run)
    monkeypatch.setattr("auto_broll.core.retime.probe_video_frame_count", lambda path: 201)

    with pytest.raises(RuntimeError, match="expected 202 frames"):
        generate_retimed_media(source, tmp_path / "retimes", "896", 195, 202, 25.0)


def test_probe_video_frame_count_uses_fast_metadata_without_count_frames(monkeypatch):
    captured = {}

    def fake_run(command, check, capture_output, text, timeout=None):
        captured["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout='{"streams":[{"nb_frames":"202","duration":"8.08","avg_frame_rate":"25/1"}]}',
            stderr="",
        )

    monkeypatch.setattr("auto_broll.core.retime.subprocess.run", fake_run)

    assert probe_video_frame_count("/broll/C896.MP4") == 202
    assert "-count_frames" not in captured["command"]


def test_probe_video_frame_count_falls_back_to_duration_times_fps(monkeypatch):
    def fake_run(command, check, capture_output, text, timeout=None):
        return SimpleNamespace(
            returncode=0,
            stdout='{"streams":[{"nb_frames":"N/A","duration":"8.08","avg_frame_rate":"25/1"}]}',
            stderr="",
        )

    monkeypatch.setattr("auto_broll.core.retime.subprocess.run", fake_run)

    assert probe_video_frame_count("/broll/C896.MP4") == 202
