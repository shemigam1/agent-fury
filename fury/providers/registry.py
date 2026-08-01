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
from fury.obs.pricing import price_for
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
        # "-latest" tracks the current flash model and stays on a live quota tier.
        "flash": "gemini-flash-latest",
        "flash-lite": "gemini-flash-lite-latest",
        "flash-2.0": "gemini-2.0-flash-001",
        "pro": "gemini-1.5-pro-002",
    },
    "openai": {"4o": "gpt-4o", "4o-mini": "gpt-4o-mini"},
    "anthropic": {
        "sonnet": "claude-sonnet-4-5",
        "haiku": "claude-haiku-4-5",
        "opus": "claude-opus-4-1",
    },
}



# Approximate context windows (tokens), matched by substring.
_WINDOWS = {
    "gemini-1.5-pro": 2_000_000,
    "gemini-flash": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    "gemini-2.5-flash": 1_000_000,
    "gpt-4o": 128_000,
    "claude": 200_000,
    "deepseek": 64_000,
    "llama-3.1": 128_000,
}


def _window(model: str) -> int:
    for key, win in _WINDOWS.items():
        if key in model:
            return win
    return 128_000


def _meta(system: str, label: str, model: str) -> ProviderMeta:
    pin, pout = price_for(model)
    return ProviderMeta(
        system=system, label=label, model=model,
        context_window=_window(model), price_in=pin, price_out=pout,
    )


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
