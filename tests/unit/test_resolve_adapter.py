import importlib

import pytest

from auto_broll.resolve.adapter import ResolveApiError, check_result


def test_check_result_rejects_none_and_false_with_context():
    with pytest.raises(ResolveApiError, match="timeline.GetItemListInTrack.*V2"):
        check_result("timeline.GetItemListInTrack", None, context="V2")

    with pytest.raises(ResolveApiError, match="project.DuplicateTimeline"):
        check_result("project.DuplicateTimeline", False)


def test_check_result_allows_other_falsey_values():
    assert check_result("empty list", []) == []
    assert check_result("zero", 0) == 0
    assert check_result("empty string", "") == ""


def test_connect_raises_actionable_error_when_resolve_script_module_missing(monkeypatch):
    import auto_broll.resolve.connection as connection

    def fake_import_module(name):
        if name == "DaVinciResolveScript":
            raise ModuleNotFoundError(name)
        return importlib.import_module(name)

    monkeypatch.setattr(connection.importlib, "import_module", fake_import_module)

    with pytest.raises(ResolveApiError) as exc_info:
        connection.connect()

    message = str(exc_info.value)
    assert "DaVinci Resolve scripting" in message
    assert "RESOLVE_SCRIPT_API" in message


def test_safe_wrappers_raise_clear_errors_for_missing_required_objects():
    from auto_broll.resolve.duplicate import duplicate_current_timeline
    from auto_broll.resolve.placement import append_video_only_clip
    from auto_broll.resolve.track import ensure_auto_broll_track

    with pytest.raises(ResolveApiError, match="project is required"):
        duplicate_current_timeline(None)

    with pytest.raises(ResolveApiError, match="timeline is required"):
        ensure_auto_broll_track(None)

    with pytest.raises(ResolveApiError, match="trackIndex"):
        append_video_only_clip(media_pool=object(), media_pool_item=object(), record_frame=0, duration=10, track_index=None)


class FakeMediaPoolItem:
    def __init__(self, values):
        self.values = values

    def GetClipProperty(self, key):
        return self.values.get(key)


def test_media_pool_item_frame_count_prefers_frames_property():
    from auto_broll.resolve.placement import media_pool_item_frame_count

    assert media_pool_item_frame_count(FakeMediaPoolItem({"Frames": "102629"})) == 102629


def test_media_pool_item_frame_count_falls_back_to_duration_timecode_and_fps():
    from auto_broll.resolve.placement import media_pool_item_frame_count

    assert media_pool_item_frame_count(FakeMediaPoolItem({"Frames": "", "Duration": "00:00:10:05", "FPS": "30.0"})) == 305


def test_build_video_only_clip_info_enforces_track_and_video_only_shape():
    from auto_broll.resolve.placement import VIDEO_ONLY_MEDIA_TYPE, build_video_only_clip_info

    item = object()
    clip_info = build_video_only_clip_info(item, record_frame=108000, duration=88, track_index=3)

    assert clip_info == {
        "mediaPoolItem": item,
        "startFrame": 0,
        "endFrame": 88,
        "recordFrame": 108000,
        "trackIndex": 3,
        "mediaType": VIDEO_ONLY_MEDIA_TYPE,
    }
