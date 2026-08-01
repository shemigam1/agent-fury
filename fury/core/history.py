"""Provider-neutral conversation model.

This is the backbone that lets agent-fury switch LLM providers *mid-session*
without losing context. The conversation is stored once, in a canonical form,
and each provider adapter (see ``fury/providers``) translates it to/from its own
native wire format on every call. Nothing about the history is Gemini-, OpenAI-,
or Anthropic-specific.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Iterable, Literal, Union

Role = Literal["system", "user", "assistant", "tool"]

# Monotonic tool-call id generator. We assign our *own* ids at parse time and
# ignore whatever a provider returns, so that re-serializing the same history to
# a *different* provider always produces internally-consistent call/result ids.
_counter = itertools.count(1)


def new_call_id() -> str:
    return f"call_{next(_counter):04d}"


@dataclass
class TextPart:
    text: str
    kind: str = field(default="text", init=False)


@dataclass
class ToolCallPart:
    """A model's request to invoke a tool."""

    id: str
    name: str
    args: dict
    kind: str = field(default="tool_call", init=False)


@dataclass
class ToolResultPart:
    """The result of executing a tool, fed back to the model."""

    id: str
    name: str
    output: str
    is_error: bool = False
    kind: str = field(default="tool_result", init=False)


ContentPart = Union[TextPart, ToolCallPart, ToolResultPart]


@dataclass
class Message:
    role: Role
    parts: list[ContentPart]

    def text(self) -> str:
        return "".join(p.text for p in self.parts if isinstance(p, TextPart))

    def tool_calls(self) -> list[ToolCallPart]:
        return [p for p in self.parts if isinstance(p, ToolCallPart)]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )


class History:
    """An ordered list of canonical messages, plus convenience mutators."""

    def __init__(self, messages: Iterable[Message] | None = None) -> None:
        self.messages: list[Message] = list(messages or [])

    def __iter__(self):
        return iter(self.messages)

    def __len__(self) -> int:
        return len(self.messages)

    def add_user(self, text: str) -> None:
        self.messages.append(Message("user", [TextPart(text)]))

    def add_assistant(self, parts: list[ContentPart]) -> None:
        self.messages.append(Message("assistant", parts))

    def add_tool_results(self, results: list[ToolResultPart]) -> None:
        # Tool results are grouped into a single "tool" message; adapters split
        # them back out into whatever shape their provider expects.
        self.messages.append(Message("tool", list(results)))

    def last_assistant_text(self) -> str:
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg.text()
        return ""
