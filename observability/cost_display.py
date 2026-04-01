# -*- coding: utf-8 -*-
"""Token and cost tracking display.

Implements R45 from the plan.
"""
from dataclasses import dataclass, field


# Approximate pricing per 1M tokens (input/output)
_PRICING = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-3-5-haiku-20241022": (1.00, 5.00),
    "qwen-max": (2.00, 6.00),
    "qwen-plus": (0.50, 2.00),
    "deepseek-chat": (0.14, 0.28),
}


@dataclass
class TokenTracker:
    """Tracks token usage and estimated cost."""

    model_name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_calls: int = 0

    def add(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Add token counts from an API call."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_calls += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float | None:
        """Estimate cost based on model pricing."""
        pricing = _PRICING.get(self.model_name)
        if pricing is None:
            # Try partial match
            for name, prices in _PRICING.items():
                if name in self.model_name or self.model_name in name:
                    pricing = prices
                    break

        if pricing is None:
            return None

        input_price, output_price = pricing
        cost = (
            (self.input_tokens / 1_000_000) * input_price
            + (self.output_tokens / 1_000_000) * output_price
        )
        return cost

    def format_status(self) -> str:
        """Format a status line for display."""
        parts = [f"tokens: {self.total_tokens:,}"]
        cost = self.estimated_cost
        if cost is not None:
            parts.append(f"cost: ${cost:.4f}")
        parts.append(f"calls: {self.total_calls}")
        return " | ".join(parts)

    def reset(self) -> None:
        """Reset all counters."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_calls = 0
