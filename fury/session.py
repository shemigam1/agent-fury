"""Session state: the canonical history plus the currently-active provider/mode.

Because history is provider-neutral, ``switch_model`` swaps the backend while
keeping every prior turn — the whole point of the design.
"""

from __future__ import annotations

from fury.config import Config
from fury.core.history import History, Usage
from fury.modes import Mode, get_mode
from fury.providers.base import Provider
from fury.providers.registry import resolve_provider
from fury.tools import build_registry
from fury.tools.base import Tool, ToolContext


class Session:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.history = History()
        self.mode: Mode = get_mode(config.mode)
        self.provider: Provider = resolve_provider(config.model_spec, config)
        self.tools: dict[str, Tool] = build_registry(self.mode.name)
        self.tool_ctx = ToolContext(root=config.root)
        self.total_usage = Usage()
        self.total_cost = 0.0

    @property
    def tool_list(self) -> list[Tool]:
        return list(self.tools.values())

    def context_budget(self) -> int:
        """Token budget for history, leaving headroom for tools + the response."""
        window = self.provider.meta.context_window or 128_000
        return int(window * 0.6)

    def switch_model(self, spec: str) -> None:
        # resolve first so a bad spec doesn't clobber the working provider.
        self.provider = resolve_provider(spec, self.config)
        self.config.model_spec = spec

    def switch_mode(self, name: str) -> None:
        self.mode = get_mode(name)
        self.tools = build_registry(self.mode.name)
        self.config.mode = name

    def record_usage(self, usage: Usage) -> None:
        self.total_usage += usage
        self.total_cost += self.provider.cost(usage)
