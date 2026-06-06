"""Frame duration helpers."""

from __future__ import annotations


def frames_duration(start: int, end: int) -> int:
    """Return end-exclusive duration, raising for impossible frame ranges."""
    if start < 0 or end < 0:
        raise ValueError("frame positions must be non-negative")
    if end <= start:
        raise ValueError("end frame must be greater than start frame")
    return end - start


def split_half_open_segments(start: int, duration: int, count: int) -> list[tuple[int, int]]:
    """Split a half-open frame range into equal contiguous segments."""
    if start < 0:
        raise ValueError("start frame must be non-negative")
    if duration <= 0:
        raise ValueError("duration must be positive")
    if count <= 0:
        raise ValueError("segment count must be positive")

    base = duration // count
    remainder = duration % count
    segments: list[tuple[int, int]] = []
    cursor = start
    for index in range(count):
        segment_duration = base + (1 if index < remainder else 0)
        end = cursor + segment_duration
        segments.append((cursor, end))
        cursor = end
    return segments


def retime_speed_percent(source_frames: int, target_frames: int) -> float | None:
    """Return slowdown speed percent only when source is shorter than target."""
    if source_frames <= 0 or target_frames <= 0:
        raise ValueError("frame counts must be positive")
    if source_frames >= target_frames:
        return None
    return (source_frames / target_frames) * 100
