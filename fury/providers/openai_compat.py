"""OpenAI-compatible adapter.

One adapter, many backends: OpenAI, OpenRouter (hosted open-source models),
Ollama and LM Studio (local), vLLM — they all speak the OpenAI Chat Completions
API. Only the ``base_url`` (and key) differ.
"""

from __future__ import annotations

import json

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


class OpenAICompatProvider(Provider):
    def __init__(
        self, meta: ProviderMeta, api_key: str, base_url: str | None = None
    ) -> None:
        super().__init__(meta)
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise ProviderNotAvailable(
                "the 'openai' package is required for OpenAI-compatible providers "
                "(pip install 'agent-fury[openai]')"
            ) from e
        if not api_key:
            raise ProviderNotAvailable(
                f"no API key for {meta.label}; set the appropriate *_API_KEY"
            )
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def _messages(self, system: str, history: History) -> list[dict]:
        msgs: list[dict] = [{"role": "system", "content": system}]
        for msg in history:
            if msg.role == "user":
                msgs.append({"role": "user", "content": msg.text()})
            elif msg.role == "assistant":
                entry: dict = {"role": "assistant", "content": msg.text() or None}
                calls = [
                    {
                        "id": p.id,
                        "type": "function",
                        "function": {
                            "name": p.name,
                            "arguments": json.dumps(p.args),
                        },
                    }
                    for p in msg.parts
                    if isinstance(p, ToolCallPart)
                ]
                if calls:
                    entry["tool_calls"] = calls
                msgs.append(entry)
            elif msg.role == "tool":
                for p in msg.parts:
                    if isinstance(p, ToolResultPart):
                        msgs.append(
                            {
                                "role": "tool",
                                "tool_call_id": p.id,
                                "content": p.output,
                            }
                        )
        return msgs

    def _tools(self, tools: list[Tool]) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def generate(
        self, system: str, history: History, tools: list[Tool]
    ) -> ProviderResponse:
        kwargs: dict = {
            "model": self.meta.model,
            "messages": self._messages(system, history),
        }
        native_tools = self._tools(tools)
        if native_tools:
            kwargs["tools"] = native_tools
            kwargs["tool_choice"] = "auto"
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"{self.meta.label} request failed: {e}") from e

        choice = resp.choices[0].message
        tool_calls = []
        for tc in choice.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCallPart(new_call_id(), tc.function.name, args))

        usage = Usage()
        if resp.usage:
            usage = Usage(
                resp.usage.prompt_tokens or 0, resp.usage.completion_tokens or 0
            )

        return ProviderResponse(
            text=choice.content or "", tool_calls=tool_calls, usage=usage, raw=resp
        )
