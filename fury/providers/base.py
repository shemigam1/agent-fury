"""Provider abstraction.

Every adapter takes the canonical ``History`` + a list of ``Tool`` objects and
returns a normalized ``ProviderResponse``. Because the adapter is the only thing
that knows a provider's wire format, the rest of agent-fury stays provider-neutral
and models can be swapped mid-session.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from fury.core.history import History, ToolCallPart, Usage
from fury.tools.base import Tool


@dataclass
class ProviderMeta:
    system: str  # OTel gen_ai.system value: "gemini" | "openai" | "anthropic"
    label: str  # human-friendly, e.g. "openrouter" / "ollama"
    model: str
    context_window: int = 0
    price_in: float = 0.0  # USD per 1M input tokens
    price_out: float = 0.0  # USD per 1M output tokens

    @property
    def spec(self) -> str:
        return f"{self.label}:{self.model}"


@dataclass
class ProviderResponse:
    text: str
    tool_calls: list[ToolCallPart] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    raw: object = None


class Provider(ABC):
    """Base class for all LLM backends."""

    def __init__(self, meta: ProviderMeta) -> None:
        self.meta = meta

    @abstractmethod
    def generate(
        self, system: str, history: History, tools: list[Tool]
    ) -> ProviderResponse:
        """One turn: send system + history + tool specs, get a response back."""

    def cost(self, usage: Usage) -> float:
        return (
            usage.input_tokens * self.meta.price_in
            + usage.output_tokens * self.meta.price_out
        ) / 1_000_000
