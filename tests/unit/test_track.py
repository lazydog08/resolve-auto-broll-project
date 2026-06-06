import pytest

from auto_broll.resolve.adapter import ResolveApiError
from auto_broll.resolve.track import clear_auto_broll_track, ensure_auto_broll_track


class Timeline:
    def __init__(self, count=4, names=None):
        self.count = count
        self.names = names or {1: "V1", 2: "V2", 3: "V3", 4: "V4"}
        self.add_calls = []
        self.set_calls = []

    def GetTrackCount(self, track_type):
        return self.count

    def GetTrackName(self, track_type, index):
        return self.names.get(index, "")

    def AddTrack(self, track_type, options=None):
        self.add_calls.append((track_type, options))
        self.count += 1
        return True

    def SetTrackName(self, track_type, index, name):
        self.set_calls.append((track_type, index, name))
        self.names[index] = name
        return True


def test_ensure_auto_broll_track_reuses_existing_track():
    timeline = Timeline(names={1: "V1", 2: "V2", 3: "AUTO_BROLL"})

    assert ensure_auto_broll_track(timeline) == 3
    assert timeline.add_calls == []


def test_ensure_auto_broll_track_inserts_at_v3_when_tracks_already_exist():
    timeline = Timeline(count=10)

    index = ensure_auto_broll_track(timeline, preferred_index=3, track_name="AUTO_BROLL")

    assert index == 3
    assert timeline.add_calls == [("video", {"index": 3})]
    assert timeline.set_calls == [("video", 3, "AUTO_BROLL")]


def test_ensure_auto_broll_track_appends_until_v3_when_only_v1_v2_exist():
    timeline = Timeline(count=2, names={1: "V1", 2: "V2"})

    index = ensure_auto_broll_track(timeline, preferred_index=3, track_name="AUTO_BROLL")

    assert index == 3
    assert timeline.add_calls == [("video", None)]
    assert timeline.set_calls == [("video", 3, "AUTO_BROLL")]


class FakeMediaPoolItem:
    def __init__(self, path):
        self.path = path

    def GetClipProperty(self, key):
        return self.path if key in {"File Path", "FilePath", "Path"} else None


class FakeTrackItem:
    def __init__(self, start, path):
        self.start = start
        self.path = path

    def GetStart(self):
        return self.start

    def GetMediaPoolItem(self):
        return FakeMediaPoolItem(self.path)


class ClearTimeline:
    def __init__(self, items):
        self.items = items
        self.deleted = None

    def GetItemListInTrack(self, track_type, track_index):
        return self.items

    def DeleteClips(self, items, ripple=False):
        self.deleted = (items, ripple)
        return True


def test_clear_auto_broll_track_deletes_matching_previous_generated_items_without_ripple():
    item = FakeTrackItem(100, "/broll/C888.MP4")
    timeline = ClearTimeline([item])

    deleted_count = clear_auto_broll_track(timeline, 3, expected_clips=[(100, "/broll/C888.MP4")])

    assert deleted_count == 1
    assert timeline.deleted == ([item], False)


def test_clear_auto_broll_track_reports_collision_for_unexpected_items_by_default():
    timeline = ClearTimeline([FakeTrackItem(100, "/broll/manual.mov")])

    with pytest.raises(ResolveApiError, match="AUTO_BROLL collision"):
        clear_auto_broll_track(timeline, 3, expected_clips=[(100, "/broll/C888.MP4")])


def test_clear_auto_broll_track_can_delete_unexpected_items_when_explicitly_enabled():
    item = FakeTrackItem(100, "/broll/manual.mov")
    timeline = ClearTimeline([item])

    deleted_count = clear_auto_broll_track(timeline, 3, expected_clips=[], clear_target_track=True)

    assert deleted_count == 1
    assert timeline.deleted == ([item], False)
