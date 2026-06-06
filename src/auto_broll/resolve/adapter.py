from __future__ import annotations

from typing import TypeVar


class ResolveApiError(RuntimeError):
    """Raised when a required Resolve scripting API call fails."""


T = TypeVar("T")


def check_result(name: str, value: T, context: str = "") -> T:
    if value is None or value is False:
        detail = f" ({context})" if context else ""
        raise ResolveApiError(f"{name} failed{detail}")
    return value
