import sys
import types

import pytest


@pytest.fixture(autouse=True)
def fake_shot_parser(monkeypatch):
    module = types.ModuleType("auto_broll.core.shot_parser")

    def parse_shot_id(raw_text, pad_width=3):
        digits = "".join(ch for ch in raw_text if ch.isdigit())
        return digits.zfill(pad_width) if digits else None

    module.parse_shot_id = parse_shot_id
    monkeypatch.setitem(sys.modules, "auto_broll.core.shot_parser", module)


class FakeTimeline:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def GetItemListInTrack(self, track_type, track_index):
        self.calls.append((track_type, track_index))
        return self.items


class FakeItem:
    def __init__(
        self,
        *,
        name="Text+ guide",
        start=100,
        end=160,
        duration=60,
        comp=None,
        notes=None,
    ):
        self.name = name
        self.start = start
        self.end = end
        self.duration = duration
        self.comp = comp
        self.notes = notes

    def GetName(self):
        return self.name

    def GetStart(self):
        return self.start

    def GetEnd(self):
        return self.end

    def GetDuration(self):
        return self.duration

    def GetFusionCompByIndex(self, index):
        assert index == 1
        return self.comp

    def GetClipProperty(self, key):
        assert key == "Notes"
        return self.notes


class FakeComp:
    def __init__(self, tools, current_time=12):
        self.tools = tools
        self.CurrentTime = current_time

    def GetToolList(self, selected_only):
        assert selected_only is False
        return self.tools


class FakeTool:
    def __init__(self, reg_id="TextPlus", styled_text="镜头001", require_time=False):
        self.reg_id = reg_id
        self.styled_text = styled_text
        self.require_time = require_time
        self.calls = []

    def GetAttrs(self):
        return {"TOOLS_RegID": self.reg_id}

    def GetInput(self, name, *args):
        self.calls.append((name, args))
        if name != "StyledText":
            return None
        if self.require_time and not args:
            raise TypeError("current time required")
        return self.styled_text


def test_reads_textplus_styled_text_from_v2_track():
    from auto_broll.resolve.textplus import read_textplus_guides_from_timeline

    timeline = FakeTimeline([FakeItem(comp=FakeComp({1: FakeTool(styled_text="镜头001")}))])

    guides = read_textplus_guides_from_timeline(timeline)

    assert timeline.calls == [("video", 2)]
    assert guides[0].track == "V2"
    assert guides[0].item_index == 0
    assert guides[0].name == "Text+ guide"
    assert guides[0].start == 100
    assert guides[0].end == 160
    assert guides[0].duration == 60
    assert guides[0].raw_text == "镜头001"
    assert guides[0].normalized_shot_id == "001"
    assert guides[0].source == "StyledText"


def test_reads_styled_text_with_current_time_when_required():
    from auto_broll.resolve.textplus import read_textplus_guides_from_timeline

    tool = FakeTool(styled_text="shot 7", require_time=True)
    timeline = FakeTimeline([FakeItem(comp=FakeComp([tool], current_time=55))])

    guides = read_textplus_guides_from_timeline(timeline, pad_width=3)

    assert guides[0].raw_text == "shot 7"
    assert guides[0].normalized_shot_id == "007"
    assert tool.calls == [("StyledText", ()), ("StyledText", (55,))]


def test_falls_back_to_notes_when_styled_text_is_empty():
    from auto_broll.resolve.textplus import read_textplus_guides_from_timeline

    timeline = FakeTimeline(
        [
            FakeItem(
                comp=FakeComp({1: FakeTool(styled_text="")}),
                notes="C042",
            )
        ]
    )

    guides = read_textplus_guides_from_timeline(timeline)

    assert guides[0].raw_text == "C042"
    assert guides[0].normalized_shot_id == "042"
    assert guides[0].source == "Notes"


def test_does_not_guess_from_name_when_styled_text_and_notes_are_missing():
    from auto_broll.resolve.textplus import read_textplus_guides_from_timeline

    timeline = FakeTimeline([FakeItem(name="Text+ C999", comp=None, notes="")])

    guides = read_textplus_guides_from_timeline(timeline)

    assert guides[0].raw_text == ""
    assert guides[0].normalized_shot_id is None
    assert guides[0].source == "Unavailable"


def test_skips_unavailable_non_guide_items_by_default():
    from auto_broll.resolve.textplus import read_textplus_guides_from_timeline

    timeline = FakeTimeline(
        [
            FakeItem(name="交叉叠化", comp=None, notes=""),
            FakeItem(comp=FakeComp({1: FakeTool(styled_text="C001")})),
        ]
    )

    guides = read_textplus_guides_from_timeline(timeline)

    assert len(guides) == 1
    assert guides[0].normalized_shot_id == "001"
