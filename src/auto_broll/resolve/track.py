from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Any, Iterator

from .adapter import ResolveApiError, check_result


AUTO_BROLL_TRACK_NAME = "AUTO_BROLL"


def ensure_auto_broll_track(
    timeline: Any,
    preferred_index: int = 3,
    track_name: str = AUTO_BROLL_TRACK_NAME,
) -> int:
    if timeline is None:
        raise ResolveApiError("timeline is required to ensure AUTO_BROLL track")

    existing_index = find_video_track_by_name(timeline, track_name)
    if existing_index is not None:
        return existing_index

    count = _video_track_count(timeline)
    target_index = preferred_index
    if count >= preferred_index:
        check_result(
            "timeline.AddTrack",
            timeline.AddTrack("video", {"index": preferred_index}),
            context=f"AUTO_BROLL index={preferred_index}",
        )
    else:
        while _video_track_count(timeline) < target_index:
            check_result("timeline.AddTrack", timeline.AddTrack("video"), context="AUTO_BROLL")

    check_result(
        "timeline.SetTrackName",
        timeline.SetTrackName("video", target_index, track_name),
        context=f"trackIndex={target_index}",
    )
    return target_index


def find_video_track_by_name(timeline: Any, track_name: str = AUTO_BROLL_TRACK_NAME) -> int | None:
    if timeline is None:
        raise ResolveApiError("timeline is required to find a video track")

    get_track_name = getattr(timeline, "GetTrackName", None)
    if get_track_name is None:
        return None

    for index in range(1, _video_track_count(timeline) + 1):
        name = check_result("timeline.GetTrackName", get_track_name("video", index), context=f"trackIndex={index}")
        if name == track_name:
            return index
    return None


def clear_auto_broll_track(
    timeline: Any,
    track_index: int,
    expected_clips: list[tuple[int, str]],
    clear_target_track: bool = False,
) -> int:
    """Clear generated AUTO_BROLL items without touching other tracks."""
    if timeline is None:
        raise ResolveApiError("timeline is required to clear AUTO_BROLL track")

    items = list(timeline.GetItemListInTrack("video", track_index) or [])
    if not items:
        return 0

    if not clear_target_track:
        unexpected = [
            item for item in items if not _item_matches_expected_clip(item, expected_clips)
        ]
        if unexpected:
            raise ResolveApiError(
                f"AUTO_BROLL collision: {len(unexpected)} existing clip(s) do not match this run; "
                "set clear_target_track=true to replace them"
            )

    check_result(
        "timeline.DeleteClips",
        timeline.DeleteClips(items, False),
        context=f"trackIndex={track_index}, ripple=False",
    )
    return len(items)


def set_video_track_lock(timeline: Any, track_index: int, locked: bool) -> None:
    if timeline is None:
        raise ResolveApiError("timeline is required to lock a video track")
    check_result(
        "timeline.SetTrackLock",
        timeline.SetTrackLock("video", track_index, locked),
        context=f"trackIndex={track_index}",
    )


def is_video_track_locked(timeline: Any, track_index: int) -> bool:
    if timeline is None:
        raise ResolveApiError("timeline is required to read video track lock state")
    value = timeline.GetIsTrackLocked("video", track_index)
    if value is None:
        raise ResolveApiError(f"timeline.GetIsTrackLocked failed (trackIndex={track_index})")
    return bool(value)


@contextmanager
def locked_video_track(timeline: Any, track_index: int) -> Iterator[None]:
    was_locked = is_video_track_locked(timeline, track_index)
    if not was_locked:
        set_video_track_lock(timeline, track_index, True)
    try:
        yield
    finally:
        if not was_locked:
            set_video_track_lock(timeline, track_index, False)


def _video_track_count(timeline: Any) -> int:
    return int(check_result("timeline.GetTrackCount", timeline.GetTrackCount("video"), context="video"))


def _item_matches_expected_clip(item: Any, expected_clips: list[tuple[int, str]]) -> bool:
    try:
        start = int(item.GetStart())
    except Exception:
        return False
    path = _item_path(item)
    if not path:
        return False
    normalized_path = _normalize_path(path)
    basename = os.path.basename(normalized_path).lower()
    for expected_start, expected_path in expected_clips:
        if start != expected_start:
            continue
        normalized_expected = _normalize_path(expected_path)
        if normalized_path == normalized_expected:
            return True
        if basename == os.path.basename(normalized_expected).lower():
            return True
    return False


def _item_path(item: Any) -> str | None:
    media_item = item.GetMediaPoolItem() if hasattr(item, "GetMediaPoolItem") else None
    if not media_item or not hasattr(media_item, "GetClipProperty"):
        return None
    for key in ("File Path", "FilePath", "Path"):
        try:
            value = media_item.GetClipProperty(key)
        except Exception:
            value = None
        if value:
            return str(value)
    return None


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))
