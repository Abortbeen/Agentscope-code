# -*- coding: utf-8 -*-
"""Simple token counting utilities."""


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English, ~2 for CJK."""
    if not text:
        return 0
    # Simple heuristic
    return max(1, len(text) // 3)
