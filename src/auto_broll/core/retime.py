from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def generated_retime_path(
    source_path: str | Path,
    output_dir: str | Path,
    shot_id: str,
    source_frames: int,
    target_frames: int,
    timeline_fps: float,
) -> Path:
    source = Path(source_path)
    fingerprint = hashlib.sha1(str(source.resolve()).encode("utf-8")).hexdigest()[:12]
    fps_token = str(timeline_fps).replace(".", "p")
    filename = f"shot{shot_id}_{source.stem}_{source_frames}to{target_frames}_{fps_token}_{fingerprint}.mp4"
    return Path(output_dir).expanduser().resolve() / filename


def build_ffmpeg_retime_command(
    source_path: str | Path,
    output_path: str | Path,
    source_frames: int,
    target_frames: int,
    timeline_fps: float,
) -> list[str]:
    if source_frames <= 0 or target_frames <= 0:
        raise ValueError("source_frames and target_frames must be positive")
    if timeline_fps <= 0:
        raise ValueError("timeline_fps must be positive")

    pts_multiplier = target_frames / source_frames
    video_filter = (
        f"setpts={pts_multiplier}*PTS,"
        f"fps={timeline_fps},"
        f"trim=start_frame=0:end_frame={target_frames},"
        "setpts=PTS-STARTPTS"
    )
    return [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(source_path),
        "-an",
        "-vf",
        video_filter,
        "-frames:v",
        str(target_frames),
        "-r",
        str(timeline_fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]


def generate_retimed_media(
    source_path: str | Path,
    output_dir: str | Path,
    shot_id: str,
    source_frames: int,
    target_frames: int,
    timeline_fps: float,
) -> str:
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"source media not found: {source}")
    output = generated_retime_path(source, output_dir, shot_id, source_frames, target_frames, timeline_fps)
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists() and probe_video_frame_count(output) == target_frames:
        return str(output)

    command = build_ffmpeg_retime_command(source, output, source_frames, target_frames, timeline_fps)
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg not found for generated retime fallback") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"ffmpeg retime failed: {detail}") from exc

    frame_count = probe_video_frame_count(output)
    if frame_count != target_frames:
        raise RuntimeError(f"generated retime expected {target_frames} frames, got {frame_count}")
    return str(output)


def probe_video_frame_count(path: str | Path) -> int | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=nb_frames,duration,avg_frame_rate,r_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    except subprocess.TimeoutExpired:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    streams = data.get("streams") if isinstance(data, dict) else None
    if not streams:
        return None
    stream = streams[0] or {}
    frame_count = _coerce_positive_int(stream.get("nb_frames"))
    if frame_count is not None:
        return frame_count
    duration = _coerce_positive_float(stream.get("duration"))
    fps = _parse_rate(stream.get("avg_frame_rate")) or _parse_rate(stream.get("r_frame_rate"))
    if duration and fps:
        return int(round(duration * fps))
    return None


def _coerce_positive_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _coerce_positive_float(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_rate(value: object) -> float | None:
    text = str(value or "")
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return float(numerator) / denominator_value
        except ValueError:
            return None
    return _coerce_positive_float(text)
