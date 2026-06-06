from __future__ import annotations

import importlib
import os
import sys
from typing import Any

from .adapter import ResolveApiError, check_result


DEFAULT_SCRIPT_MODULES = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
SCRIPTING_ENV_HELP = (
    "DaVinci Resolve scripting module is not available. Set the Resolve scripting env first: "
    "RESOLVE_SCRIPT_API, RESOLVE_SCRIPT_LIB, and PYTHONPATH should point at the Resolve Developer "
    "Scripting paths for this machine."
)


def _load_scriptapp() -> Any:
    _ensure_script_module_path()
    try:
        module = importlib.import_module("DaVinciResolveScript")
    except ModuleNotFoundError as exc:
        raise ResolveApiError(SCRIPTING_ENV_HELP) from exc

    scriptapp = getattr(module, "scriptapp", None)
    if scriptapp is None:
        raise ResolveApiError("DaVinci Resolve scripting module loaded, but scriptapp is missing.")
    return scriptapp


def _ensure_script_module_path() -> None:
    candidates: list[str] = []
    api_root = os.environ.get("RESOLVE_SCRIPT_API")
    if api_root:
        candidates.append(os.path.join(api_root, "Modules"))
    candidates.append(DEFAULT_SCRIPT_MODULES)

    for candidate in candidates:
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.append(candidate)


def connect(app_name: str = "Resolve") -> Any:
    scriptapp = _load_scriptapp()
    try:
        resolve = scriptapp(app_name)
    except Exception as exc:  # Resolve's scriptapp can fail with non-Pythonic errors.
        raise ResolveApiError(f"DaVinci Resolve scripting connect failed: {exc}") from exc
    return check_result("DaVinciResolveScript.scriptapp", resolve, context=app_name)


def get_project_manager(resolve: Any) -> Any:
    return check_result("resolve.GetProjectManager", resolve.GetProjectManager())


def get_current_project(resolve: Any) -> Any:
    manager = get_project_manager(resolve)
    return check_result("projectManager.GetCurrentProject", manager.GetCurrentProject())


def get_current_timeline(project: Any) -> Any:
    return check_result("project.GetCurrentTimeline", project.GetCurrentTimeline())
