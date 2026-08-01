"""Google Gemini adapter (google-genai)."""

from __future__ import annotations

import re
import time

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

_JSON_TO_GENAI = {
    "object": "OBJECT",
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
}


def _to_genai_schema(types_mod, js: dict):
    t = js.get("type", "object")
    schema = types_mod.Schema(type=getattr(types_mod.Type, _JSON_TO_GENAI[t]))
    if js.get("description"):
        schema.description = js["description"]
    if t == "object":
        props = js.get("properties", {})
        if props:
            schema.properties = {
                k: _to_genai_schema(types_mod, v) for k, v in props.items()
            }
        if js.get("required"):
            schema.required = js["required"]
    elif t == "array":
        schema.items = _to_genai_schema(types_mod, js["items"])
    return schema


class GeminiProvider(Provider):
    def __init__(self, meta: ProviderMeta, api_key: str) -> None:
        super().__init__(meta)
        if not api_key:
            raise ProviderNotAvailable("GEMINI_API_KEY is not set")
        try:
            from google import genai
        except ImportError as e:  # pragma: no cover
            raise ProviderNotAvailable("google-genai is not installed") from e
        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    # -- canonical -> native ------------------------------------------------
    def _contents(self, history: History):
        types = self._genai.types
        contents = []
        for msg in history:
            if msg.role == "user":
                contents.append(
                    types.Content(role="user", parts=[types.Part(text=msg.text())])
                )
            elif msg.role == "assistant":
                parts = []
                for p in msg.parts:
                    if isinstance(p, TextPart) and p.text:
                        parts.append(types.Part(text=p.text))
                    elif isinstance(p, ToolCallPart):
                        part = types.Part(
                            function_call=types.FunctionCall(
                                name=p.name, args=p.args
                            )
                        )
                        # Replay the thought_signature that Gemini "thinking"
                        # models require when a prior function call is sent back.
                        if p.signature is not None:
                            part.thought_signature = p.signature
                        parts.append(part)
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif msg.role == "tool":
                parts = []
                for p in msg.parts:
                    if isinstance(p, ToolResultPart):
                        payload = (
                            {"error": p.output} if p.is_error else {"result": p.output}
                        )
                        parts.append(
                            types.Part.from_function_response(
                                name=p.name, response=payload
                            )
                        )
                # Gemini function responses must use role "user" — the API does
                # not accept a "tool"/"function" role for content.
                contents.append(types.Content(role="user", parts=parts))
        return contents

    def _tools(self, tools: list[Tool]):
        types = self._genai.types
        if not tools:
            return None
        decls = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=_to_genai_schema(types, t.parameters),
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=decls)]

    # -- resilience ---------------------------------------------------------
    def _with_retry(self, call, max_attempts: int = 4):
        """Retry on 429/RESOURCE_EXHAUSTED, honoring the server's retry delay.

        Free tiers are rate-limited (e.g. a few requests/minute), and a single
        agent task makes several calls — so basic backoff is what makes the tool
        usable rather than failing halfway through a task.
        """
        for attempt in range(1, max_attempts + 1):
            try:
                return call()
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                # 429 = rate limited; 503/500 = transient server overload/errors.
                retryable = any(
                    tok in msg
                    for tok in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE",
                                "500", "INTERNAL")
                )
                # A per-day quota won't recover within a retry window — fail fast.
                if "PerDay" in msg or "GenerateRequestsPerDay" in msg:
                    retryable = False
                if not retryable or attempt == max_attempts:
                    raise ProviderError(f"Gemini request failed: {e}") from e
                time.sleep(min(self._retry_delay(msg) or 2 ** attempt, 60))

    @staticmethod
    def _retry_delay(msg: str) -> float:
        m = re.search(r"retry in ([\d.]+)s", msg) or re.search(
            r"retryDelay['\"]?:\s*['\"]?(\d+)s", msg
        )
        return float(m.group(1)) + 0.5 if m else 0.0

    # -- native -> canonical ------------------------------------------------
    def generate(
        self, system: str, history: History, tools: list[Tool]
    ) -> ProviderResponse:
        types = self._genai.types
        config = types.GenerateContentConfig(
            tools=self._tools(tools),
            system_instruction=system,
        )
        response = self._with_retry(
            lambda: self._client.models.generate_content(
                model=self.meta.model,
                contents=self._contents(history),
                config=config,
            )
        )

        usage = Usage()
        if response.usage_metadata:
            usage = Usage(
                response.usage_metadata.prompt_token_count or 0,
                response.usage_metadata.candidates_token_count or 0,
            )

        # Iterate parts directly so we can pair each function_call with its
        # thought_signature (and avoid response.text's function-call warning).
        text_chunks: list[str] = []
        tool_calls: list[ToolCallPart] = []
        candidates = response.candidates or []
        if candidates and candidates[0].content and candidates[0].content.parts:
            for part in candidates[0].content.parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    tool_calls.append(
                        ToolCallPart(
                            new_call_id(),
                            fc.name,
                            dict(fc.args or {}),
                            signature=getattr(part, "thought_signature", None),
                        )
                    )
                elif getattr(part, "text", None) and not getattr(part, "thought", False):
                    text_chunks.append(part.text)

        return ProviderResponse(
            text="".join(text_chunks),
            tool_calls=tool_calls,
            usage=usage,
            raw=response,
        )
