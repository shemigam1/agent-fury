"""Runtime configuration for agent-fury.

Resolution order (highest priority first):
  1. CLI flags (passed as overrides to ``Config.load``)
  2. environment / a ``.env`` file in the current directory
  3. ``~/.config/fury/config.toml``

This layering is what lets an installed, global ``fury`` work from inside any
repo — secrets and defaults live in the user's home config, while per-invocation
choices come from flags.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "gemini:flash"
DEFAULT_MODE = "code"
CONFIG_PATH = Path.home() / ".config" / "fury" / "config.toml"

# provider -> environment variable holding its API key.
_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

# provider -> (env var for base_url, default base_url)
_BASE_ENV = {
    "openai": ("OPENAI_BASE_URL", None),
    "openrouter": ("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    "ollama": ("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
}


def _read_toml() -> dict:
    if not CONFIG_PATH.is_file():
        return {}
    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


@dataclass
class Config:
    model_spec: str = DEFAULT_MODEL
    working_dir: str = "."
    mode: str = DEFAULT_MODE
    verbose: bool = False
    yolo: bool = False
    plan_only: bool = False
    max_iters: int = 40
    telemetry: bool = False
    otel_endpoint: str = "localhost:4317"
    keys: dict = field(default_factory=dict)
    base_urls: dict = field(default_factory=dict)

    root: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.root = os.path.abspath(self.working_dir)

    def key(self, provider: str) -> str:
        return self.keys.get(provider, "")

    def base_url(self, provider: str) -> str | None:
        return self.base_urls.get(provider)

    @classmethod
    def load(cls, **overrides) -> "Config":
        load_dotenv()
        file_cfg = _read_toml()
        file_keys = file_cfg.get("keys", {})
        file_base = file_cfg.get("base_urls", {})
        file_defaults = file_cfg.get("defaults", {})

        keys = {}
        for provider, env in _KEY_ENV.items():
            val = os.environ.get(env) or file_keys.get(provider)
            if val:
                keys[provider] = val

        base_urls = {}
        for provider, (env, default) in _BASE_ENV.items():
            base_urls[provider] = (
                os.environ.get(env) or file_base.get(provider) or default
            )

        tel_cfg = file_cfg.get("telemetry", {})
        env_tel = os.environ.get("FURY_TELEMETRY", "").lower() in ("1", "true", "yes")
        params = {
            "model_spec": file_defaults.get("model", DEFAULT_MODEL),
            "mode": file_defaults.get("mode", DEFAULT_MODE),
            "telemetry": env_tel or bool(tel_cfg.get("enabled", False)),
            "otel_endpoint": (
                os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
                or tel_cfg.get("endpoint")
                or "localhost:4317"
            ),
            "keys": keys,
            "base_urls": base_urls,
        }
        params.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**params)
