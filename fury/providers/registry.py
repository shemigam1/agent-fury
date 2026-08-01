"""Resolve a ``provider:model`` spec into a live ``Provider``.

Specs look like:
    gemini:flash                 (alias -> gemini-2.0-flash-001)
    openai:gpt-4o-mini
    openrouter:deepseek/deepseek-chat
    ollama:llama3.1              (local, no key needed)
    anthropic:sonnet             (alias -> a Claude model id)

A bare spec with no provider prefix (e.g. "flash") defaults to Gemini.
"""

from __future__ import annotations

from fury.core.errors import ConfigError
from fury.providers.base import Provider, ProviderMeta

# provider -> {env key, default base_url, example models} — powers `fury models`.
KNOWN_PROVIDERS = {
    "gemini": {"env": "GEMINI_API_KEY", "examples": ["flash", "flash-lite", "pro"]},
    "openai": {"env": "OPENAI_API_KEY", "examples": ["gpt-4o-mini", "gpt-4o"]},
    "openrouter": {
        "env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "examples": ["deepseek/deepseek-chat", "meta-llama/llama-3.1-70b-instruct"],
    },
    "ollama": {
        "env": None,
        "base_url": "http://localhost:11434/v1",
        "examples": ["llama3.1", "qwen2.5-coder", "deepseek-r1"],
    },
    "anthropic": {"env": "ANTHROPIC_API_KEY", "examples": ["sonnet", "haiku", "opus"]},
}

_ALIASES = {
    "gemini": {
        "flash": "gemini-2.0-flash-001",
        "flash-lite": "gemini-2.0-flash-lite-001",
        "flash-2.5": "gemini-2.5-flash",
        "pro": "gemini-1.5-pro-002",
    },
    "openai": {"4o": "gpt-4o", "4o-mini": "gpt-4o-mini"},
    "anthropic": {
        "sonnet": "claude-sonnet-4-5",
        "haiku": "claude-haiku-4-5",
        "opus": "claude-opus-4-1",
    },
}

# Rough USD/1M-token pricing for a /cost estimate. Expanded in obs/pricing (Phase 3).
# Matched by substring; unknown models are treated as free (local/self-hosted).
_PRICING = {
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
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


def _price(model: str) -> tuple[float, float]:
    for key, price in _PRICING.items():
        if key in model:
            return price
    return (0.0, 0.0)


def _meta(system: str, label: str, model: str) -> ProviderMeta:
    pin, pout = _price(model)
    return ProviderMeta(system=system, label=label, model=model, price_in=pin, price_out=pout)


def resolve_provider(spec: str, config) -> Provider:
    """Turn a spec + config into a ready-to-use Provider instance."""
    name, sep, model = spec.partition(":")
    if not sep:  # bare "flash" -> default provider
        name, model = "gemini", name
    name = name.lower().strip()
    model = _ALIASES.get(name, {}).get(model, model)
    if not model:
        raise ConfigError(f'model spec "{spec}" is missing a model name')

    if name == "gemini":
        from fury.providers.gemini import GeminiProvider

        return GeminiProvider(_meta("gemini", "gemini", model), config.key("gemini"))

    if name in ("openai", "openrouter", "ollama"):
        from fury.providers.openai_compat import OpenAICompatProvider

        base_url = config.base_url(name)
        # google's gen_ai.system for OpenAI-compatible backends is "openai".
        api_key = config.key(name) or ("ollama" if name == "ollama" else "")
        return OpenAICompatProvider(
            _meta("openai", name, model), api_key=api_key, base_url=base_url
        )

    if name == "anthropic":
        from fury.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            _meta("anthropic", "anthropic", model), config.key("anthropic")
        )

    raise ConfigError(
        f'unknown provider "{name}". Known: {", ".join(KNOWN_PROVIDERS)}'
    )
