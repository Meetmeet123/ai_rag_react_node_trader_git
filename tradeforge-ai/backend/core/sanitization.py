"""
Input sanitization helpers for user-facing fields.

Provides lightweight, dependency-tolerant utilities to strip whitespace,
limit length, remove null bytes, and sanitize HTML when bleach is available.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    import bleach

    BLEACH_AVAILABLE = True
except ImportError:  # pragma: no cover
    BLEACH_AVAILABLE = False


_RE_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_RE_EVENT_HANDLER = re.compile(
    r"on\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)


def sanitize_string(value: Optional[str], max_length: int = 1000) -> Optional[str]:
    """Strip whitespace, remove null bytes, and enforce a length limit."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    value = value.strip().replace("\x00", "")
    if len(value) > max_length:
        value = value[:max_length]
    return value


def sanitize_html(value: Optional[str]) -> Optional[str]:
    """Remove dangerous HTML; prefers bleach and falls back to regex stripping."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    if BLEACH_AVAILABLE:
        return bleach.clean(value, strip=True)

    logger.debug("bleach not installed; using regex fallback for HTML sanitization")
    value = _RE_SCRIPT.sub("", value)
    value = _RE_EVENT_HANDLER.sub("", value)
    return value


def sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize string values inside a dictionary."""
    if not isinstance(d, dict):
        return d

    result: Dict[str, Any] = {}
    for key, value in d.items():
        if isinstance(value, str):
            result[key] = sanitize_string(value)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = _sanitize_list(value)
        else:
            result[key] = value
    return result


def _sanitize_list(items: List[Any]) -> List[Any]:
    """Recursively sanitize string values inside a list."""
    result: List[Any] = []
    for item in items:
        if isinstance(item, str):
            result.append(sanitize_string(item))
        elif isinstance(item, dict):
            result.append(sanitize_dict(item))
        elif isinstance(item, list):
            result.append(_sanitize_list(item))
        else:
            result.append(item)
    return result
