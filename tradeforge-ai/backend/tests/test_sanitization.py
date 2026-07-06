"""Tests for the input sanitization utilities."""

from __future__ import annotations

from core.sanitization import sanitize_dict, sanitize_html, sanitize_string


def test_sanitize_string_trims_whitespace() -> None:
    """Whitespace is stripped from both ends."""
    assert sanitize_string("  hello world  ") == "hello world"


def test_sanitize_string_removes_null_bytes() -> None:
    """Null bytes are removed from strings."""
    assert sanitize_string("a\x00b\x00c") == "abc"


def test_sanitize_string_enforces_max_length() -> None:
    """Strings longer than max_length are truncated."""
    long_value = "x" * 2000
    assert sanitize_string(long_value, max_length=1000) == "x" * 1000


def test_sanitize_string_passes_through_none() -> None:
    """None values are returned unchanged."""
    assert sanitize_string(None) is None


def test_sanitize_string_passes_through_non_string() -> None:
    """Non-string values are returned unchanged."""
    assert sanitize_string(123) == 123  # type: ignore[arg-type]


def test_sanitize_dict_recursively_sanitizes_strings() -> None:
    """String values inside nested dicts and lists are sanitized."""
    data = {
        "name": "  test name  ",
        "nested": {"description": "  nested desc  "},
        "items": [
            {"label": "  item label  "},
            "  plain item  ",
            42,
        ],
    }
    result = sanitize_dict(data)
    assert result["name"] == "test name"
    assert result["nested"]["description"] == "nested desc"
    assert result["items"][0]["label"] == "item label"
    assert result["items"][1] == "plain item"
    assert result["items"][2] == 42


def test_sanitize_dict_removes_null_bytes() -> None:
    """Null bytes are removed from string values in a dict."""
    data = {"payload": "safe\x00value"}
    assert sanitize_dict(data)["payload"] == "safevalue"


def test_sanitize_html_strips_script_tags() -> None:
    """Script tags are removed from HTML strings."""
    dirty = '<p>hello</p><script>alert("xss")</script>'
    cleaned = sanitize_html(dirty)
    assert "<script>" not in cleaned
    assert "</script>" not in cleaned


def test_sanitize_html_strips_event_handlers() -> None:
    """Inline event handlers are removed from HTML strings."""
    dirty = '<img src="x" onerror="alert(1)">'
    cleaned = sanitize_html(dirty)
    assert "onerror" not in cleaned
