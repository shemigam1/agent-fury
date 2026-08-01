"""Native Anthropic (Claude) adapter."""

from __future__ import annotations

from fury.core.errors import ProviderError, ProviderNotAvailable
from fury.core.history import (
    History,
    TextPart,
    ToolCallPart,
    ToolResultPart,
    Usage,
    new_call_id,
)
from fury.providers.base import Provider, ProviderMeta, ProviderResponse
from fury.tools.base import Tool

DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(Provider):
    def __init__(self, meta: ProviderMeta, api_key: str) -> None:
        super().__init__(meta)
        try:
            from anthropic import Anthropic
        except ImportError as e:  # pragma: no cover
            raise ProviderNotAvailable(
                "the 'anthropic' package is required (pip install 'agent-fury[anthropic]')"
            ) from e
        if not api_key:
            raise ProviderNotAvailable("ANTHROPIC_API_KEY is not set")
        self._client = Anthropic(api_key=api_key)

    def _messages(self, history: History) -> list[dict]:
        msgs: list[dict] = []
        for msg in history:
            if msg.role == "user":
                msgs.append({"role": "user", "content": msg.text()})
            elif msg.role == "assistant":
                blocks = []
                for p in msg.parts:
                    if isinstance(p, TextPart) and p.text:
                        blocks.append({"type": "text", "text": p.text})
                    elif isinstance(p, ToolCallPart):
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": p.id,
                                "name": p.name,
                                "input": p.args,
                            }
                        )
                if blocks:
                    msgs.append({"role": "assistant", "content": blocks})
            elif msg.role == "tool":
                # Claude wants tool results in a *user* message.
                blocks = [
                    {
                        "type": "tool_result",
                        "tool_use_id": p.id,
                        "content": p.output,
                        "is_error": p.is_error,
                    }
                    for p in msg.parts
                    if isinstance(p, ToolResultPart)
                ]
                msgs.append({"role": "user", "content": blocks})
        return msgs

    def _tools(self, tools: list[Tool]) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def generate(
        self, system: str, history: History, tools: list[Tool]
    ) -> ProviderResponse:
        kwargs: dict = {
            "model": self.meta.model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "system": system,
            "messages": self._messages(history),
        }
        if tools:
            kwargs["tools"] = self._tools(tools)
        try:
            resp = self._client.messages.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"Anthropic request failed: {e}") from e

        text_parts, tool_calls = [], []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallPart(new_call_id(), block.name, dict(block.input or {}))
                )

        usage = Usage(
            getattr(resp.usage, "input_tokens", 0) or 0,
            getattr(resp.usage, "output_tokens", 0) or 0,
        )
        return ProviderResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            usage=usage,
            raw=resp,
        )
