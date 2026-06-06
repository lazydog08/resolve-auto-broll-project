from __future__ import annotations

import importlib
from typing import Any, Iterable

from auto_broll.models import TextPlusGuide

from .adapter import ResolveApiError, check_result


TEXTPLUS_REG_IDS = {"TextPlus", "Text+"}


def read_textplus_guides_from_timeline(
    timeline: Any,
    track_index: int = 2,
    pad_width: int = 3,
    include_unavailable: bool = False,
) -> list[TextPlusGuide]:
    items = check_result(
        "timeline.GetItemListInTrack",
        timeline.GetItemListInTrack("video", track_index),
        context=f"track=V{track_index}",
    )

    guides: list[TextPlusGuide] = []
    for item_index, item in enumerate(items):
        name = _required_item_value(item, "GetName", item_index)
        start = _required_item_value(item, "GetStart", item_index)
        end = _required_item_value(item, "GetEnd", item_index)
        duration = _required_item_value(item, "GetDuration", item_index)
        raw_text, source = _read_text_source(item)
        if source == "Unavailable" and not include_unavailable and not _looks_like_text_guide(item, name):
            continue
        parsed = _parse_shot_ids(raw_text, pad_width) if raw_text else []
        normalized = parsed[0].zfill(pad_width) if parsed else None

        guides.append(
            TextPlusGuide(
                track=f"V{track_index}",
                item_index=item_index,
                name=name,
                start=start,
                end=end,
                duration=duration,
                raw_text=raw_text,
                normalized_shot_id=normalized,
                source=source,
                parsed_shot_ids=parsed,
            )
        )
    return guides


def _required_item_value(item: Any, method_name: str, item_index: int) -> Any:
    method = getattr(item, method_name, None)
    if method is None:
        raise ResolveApiError(f"Timeline item {item_index} is missing {method_name}")
    return check_result(f"TimelineItem.{method_name}", method(), context=f"item_index={item_index}")


def _read_text_source(item: Any) -> tuple[str, str]:
    styled_text = _read_styled_text(item)
    if styled_text:
        return styled_text, "StyledText"

    notes = _read_notes(item)
    if notes:
        return notes, "Notes"

    return "", "Unavailable"


def _looks_like_text_guide(item: Any, name: str) -> bool:
    lowered = name.lower()
    if "text" in lowered or "text+" in lowered or "文本" in lowered:
        return True
    return bool(_safe_call(item, "GetFusionCompByIndex", 1))


def _read_styled_text(item: Any) -> str:
    comp = _safe_call(item, "GetFusionCompByIndex", 1)
    if not comp:
        return ""

    tools = _safe_call(comp, "GetToolList", False)
    if not tools:
        return ""

    for tool in _iter_tools(tools):
        attrs = _safe_call(tool, "GetAttrs")
        if not isinstance(attrs, dict):
            continue
        if attrs.get("TOOLS_RegID") not in TEXTPLUS_REG_IDS:
            continue

        text = _read_styled_text_input(tool, comp)
        if text:
            return text
    return ""


def _read_styled_text_input(tool: Any, comp: Any) -> str:
    try:
        value = tool.GetInput("StyledText")
    except Exception:
        value = None

    text = _coerce_text(value)
    if text:
        return text

    current_time = _current_time(comp)
    try:
        value = tool.GetInput("StyledText", current_time)
    except Exception:
        return ""
    return _coerce_text(value)


def _current_time(comp: Any) -> Any:
    current_time = getattr(comp, "CurrentTime", 0)
    if callable(current_time):
        try:
            return current_time()
        except Exception:
            return 0
    return current_time


def _read_notes(item: Any) -> str:
    try:
        return _coerce_text(item.GetClipProperty("Notes"))
    except Exception:
        return ""


def _iter_tools(tools: Any) -> Iterable[Any]:
    if isinstance(tools, dict):
        return tools.values()
    if isinstance(tools, (list, tuple)):
        return tools
    values = getattr(tools, "values", None)
    if callable(values):
        return values()
    return []


def _safe_call(obj: Any, method_name: str, *args: Any) -> Any:
    method = getattr(obj, method_name, None)
    if method is None:
        return None
    try:
        return method(*args)
    except Exception:
        return None


def _coerce_text(value: Any) -> str:
    if value is None or value is False:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _parse_shot_id(raw_text: str, pad_width: int) -> str | None:
    parsed = _parse_shot_ids(raw_text, pad_width)
    return parsed[0].zfill(pad_width) if parsed else None


def _parse_shot_ids(raw_text: str, pad_width: int) -> list[str]:
    module = importlib.import_module("auto_broll.core.shot_parser")
    parser = (
        getattr(module, "parse_shot_ids", None)
        or getattr(module, "parse_shot_id", None)
        or getattr(module, "normalize_shot_id", None)
        or getattr(module, "normalize", None)
    )
    if parser is None:
        raise ResolveApiError("auto_broll.core.shot_parser must expose parse_shot_id or normalize_shot_id")

    try:
        value = parser(raw_text, pad_width=pad_width)
    except TypeError:
        value = parser(raw_text, pad_width)
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value else []
