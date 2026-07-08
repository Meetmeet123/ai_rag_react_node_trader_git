"""
Lightweight prompt guard for the LLM router.

Detects common prompt-injection / jailbreak patterns and rejects them before
they reach the language model. This is a deterministic first line of defence;
it does not replace a full moderation service but blocks the majority of
naive attacks.
"""

from __future__ import annotations

import re
from typing import List

# Patterns are lower-cased before matching.
_BLOCKED_PATTERNS: List[str] = [
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"ignore\s+(?:the\s+)?system\s+prompt",
    r"you\s+are\s+not\s+(?:an\s+)?(?:ai|assistant|trading\s+assistant)",
    r"pretend\s+to\s+be",
    r"act\s+as\s+(?:if\s+)?you\s+are",
    r"new\s+instructions?:",
    r"override\s+(?:your\s+)?(?:constraints?|instructions?|programming)",
    r"disregard\s+(?:your\s+)?(?:instructions?|rules?|guidelines?)",
    r"(?:reveal|show|print|output)\s+(?:your\s+)?(?:system\s+)?prompt",
    r"(?:reveal|show|print|output)\s+(?:your\s+)?instructions",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"do\s+anything\s+now",
    r"simulate\s+(?:an\s+)?unfiltered\s+(?:ai|assistant)",
]


class PromptGuardError(ValueError):
    """Raised when a prompt fails the guard checks."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def check_prompt(text: str) -> None:
    """Raise ``PromptGuardError`` if ``text`` contains a blocked pattern."""
    lower = text.lower()
    for pattern in _BLOCKED_PATTERNS:
        if re.search(pattern, lower):
            raise PromptGuardError(
                "Prompt contains disallowed instructions and was rejected."
            )
