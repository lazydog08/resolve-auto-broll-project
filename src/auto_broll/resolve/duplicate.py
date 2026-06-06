from __future__ import annotations

from typing import Any

from .adapter import ResolveApiError, check_result


def duplicate_current_timeline(project: Any, suffix: str = "__AUTO_BROLL_v001") -> Any:
    if project is None:
        raise ResolveApiError("project is required to duplicate the current timeline")

    timeline = check_result("project.GetCurrentTimeline", project.GetCurrentTimeline())
    original_name = check_result("timeline.GetName", timeline.GetName())
    duplicate_name = next_duplicate_timeline_name(project, original_name, suffix=suffix)
    duplicate = getattr(timeline, "DuplicateTimeline", None)
    if duplicate is None:
        raise ResolveApiError("timeline.DuplicateTimeline is unavailable")
    return check_result("timeline.DuplicateTimeline", duplicate(duplicate_name), context=f"name={duplicate_name}")


def next_duplicate_timeline_name(project: Any, original_name: str, suffix: str = "__AUTO_BROLL_v001") -> str:
    existing = _timeline_names(project)
    base_suffix = _suffix_base(suffix)
    version = _suffix_version(suffix)
    while True:
        candidate = f"{original_name}{base_suffix}{version:03d}"
        if candidate not in existing:
            return candidate
        version += 1


def _suffix_base(suffix: str) -> str:
    if suffix.endswith("_v001"):
        return suffix[:-3]
    if suffix.startswith("__") and suffix.endswith("_v"):
        return suffix
    if suffix.startswith("__"):
        return f"{suffix}_v"
    return f"__{suffix}_v"


def _suffix_version(suffix: str) -> int:
    if suffix.endswith("_v001"):
        return 1
    return 1


def _timeline_names(project: Any) -> set[str]:
    get_count = getattr(project, "GetTimelineCount", None)
    get_by_index = getattr(project, "GetTimelineByIndex", None)
    if get_count is None or get_by_index is None:
        return set()

    count = check_result("project.GetTimelineCount", get_count())
    names: set[str] = set()
    for index in range(1, int(count) + 1):
        timeline = get_by_index(index)
        if timeline is None or timeline is False:
            continue
        get_name = getattr(timeline, "GetName", None)
        if get_name is None:
            continue
        name = check_result("timeline.GetName", get_name(), context=f"timeline_index={index}")
        names.add(name)
    return names
