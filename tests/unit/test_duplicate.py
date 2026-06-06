from auto_broll.resolve.duplicate import next_duplicate_timeline_name


class Timeline:
    def __init__(self, name):
        self.name = name
        self.duplicate_names = []

    def GetName(self):
        return self.name

    def DuplicateTimeline(self, name):
        self.duplicate_names.append(name)
        return Timeline(name)


class Project:
    def __init__(self, names):
        self.timelines = [Timeline(name) for name in names]

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, index):
        return self.timelines[index - 1]

    def GetCurrentTimeline(self):
        return self.timelines[0]


def test_next_duplicate_timeline_name_uses_plan_suffix_shape():
    project = Project(["Timeline 1", "Timeline 1__AUTO_BROLL_v001"])

    assert next_duplicate_timeline_name(project, "Timeline 1") == "Timeline 1__AUTO_BROLL_v002"


def test_next_duplicate_timeline_name_accepts_full_suffix_from_config():
    project = Project(["Timeline 1"])

    assert next_duplicate_timeline_name(project, "Timeline 1", suffix="__AUTO_BROLL_v001") == "Timeline 1__AUTO_BROLL_v001"


def test_duplicate_current_timeline_calls_timeline_api():
    from auto_broll.resolve.duplicate import duplicate_current_timeline

    project = Project(["Timeline 1"])

    duplicate = duplicate_current_timeline(project)

    assert duplicate.GetName() == "Timeline 1__AUTO_BROLL_v001"
    assert project.timelines[0].duplicate_names == ["Timeline 1__AUTO_BROLL_v001"]
