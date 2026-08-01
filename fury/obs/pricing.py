"""Per-model pricing (USD per 1M tokens), matched by substring.

Unknown models are treated as free (local/self-hosted). These are approximate
list prices for cost *estimates* (shown in /cost and exported as a metric), not
billing-grade figures.
"""

from __future__ import annotations

PRICING: dict[str, tuple[float, float]] = {
    # (input, output) USD per 1M tokens
    "gemini-flash-lite": (0.075, 0.30),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-flash-latest": (0.10, 0.40),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-1.5-pro": (1.25, 5.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.5, 10.0),
    "claude-haiku": (1.0, 5.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-opus": (15.0, 75.0),
    "deepseek": (0.14, 0.28),
    "llama-3.1-70b": (0.35, 0.40),
}


def price_for(model: str) -> tuple[float, float]:
    for key, price in PRICING.items():
        if key in model:
            return price
    return (0.0, 0.0)
