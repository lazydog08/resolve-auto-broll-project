from __future__ import annotations

from typing import Any

from .adapter import ResolveApiError, check_result


VIDEO_ONLY_MEDIA_TYPE = 1


def build_video_only_clip_info(
    media_pool_item: Any,
    record_frame: int,
    duration: int,
    track_index: int,
    source_start: int = 0,
) -> dict[str, Any]:
    if media_pool_item is None:
        raise ResolveApiError("mediaPoolItem is required for placement")
    if track_index is None:
        raise ResolveApiError("trackIndex is required for placement")
    if duration <= 0:
        raise ResolveApiError("duration must be positive for placement")

    return {
        "mediaPoolItem": media_pool_item,
        "startFrame": source_start,
        "endFrame": source_start + duration,
        "recordFrame": record_frame,
        "trackIndex": track_index,
        "mediaType": VIDEO_ONLY_MEDIA_TYPE,
    }


def append_video_only_clip(
    media_pool: Any,
    media_pool_item: Any,
    record_frame: int,
    duration: int,
    track_index: int,
    source_start: int = 0,
) -> Any:
    if media_pool is None:
        raise ResolveApiError("media_pool is required for placement")

    clip_info = build_video_only_clip_info(
        media_pool_item=media_pool_item,
        record_frame=record_frame,
        duration=duration,
        track_index=track_index,
        source_start=source_start,
    )
    return check_result(
        "mediaPool.AppendToTimeline",
        media_pool.AppendToTimeline([clip_info]),
        context=f"trackIndex={track_index}, mediaType={VIDEO_ONLY_MEDIA_TYPE}",
    )


def import_media(media_pool: Any, path: str) -> Any:
    if media_pool is None:
        raise ResolveApiError("media_pool is required to import media")
    if not path:
        raise ResolveApiError("path is required to import media")

    imported_items = check_result("mediaPool.ImportMedia", media_pool.ImportMedia([path]), context=path)
    if not imported_items:
        raise ResolveApiError(f"mediaPool.ImportMedia returned no items ({path})")
    return imported_items[0]


def media_pool_item_frame_count(media_pool_item: Any) -> int | None:
    if media_pool_item is None or not hasattr(media_pool_item, "GetClipProperty"):
        return None

    frames = _clip_property(media_pool_item, "Frames")
    frame_count = _coerce_int(frames)
    if frame_count is not None:
        return frame_count

    duration = _clip_property(media_pool_item, "Duration")
    fps = _coerce_float(_clip_property(media_pool_item, "FPS"))
    if duration and fps:
        return _timecode_to_frames(str(duration), fps)
    return None


def _clip_property(media_pool_item: Any, key: str) -> Any:
    try:
        return media_pool_item.GetClipProperty(key)
    except Exception:
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except ValueError:
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _timecode_to_frames(timecode: str, fps: float) -> int | None:
    parts = timecode.split(":")
    if len(parts) != 4:
        return None
    try:
        hours, minutes, seconds, frames = [int(part) for part in parts]
    except ValueError:
        return None
    rounded_fps = int(round(fps))
    return ((hours * 3600 + minutes * 60 + seconds) * rounded_fps) + frames
