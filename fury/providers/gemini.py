"""Google Gemini adapter (google-genai)."""

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
                        parts.append(
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=p.name, args=p.args
                                )
                            )
                        )
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
                contents.append(types.Content(role="tool", parts=parts))
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

    # -- native -> canonical ------------------------------------------------
    def generate(
        self, system: str, history: History, tools: list[Tool]
    ) -> ProviderResponse:
        types = self._genai.types
        try:
            response = self._client.models.generate_content(
                model=self.meta.model,
                contents=self._contents(history),
                config=types.GenerateContentConfig(
                    tools=self._tools(tools),
                    system_instruction=system,
                ),
            )
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"Gemini request failed: {e}") from e

        usage = Usage()
        if response.usage_metadata:
            usage = Usage(
                response.usage_metadata.prompt_token_count or 0,
                response.usage_metadata.candidates_token_count or 0,
            )

        tool_calls = []
        for fc in response.function_calls or []:
            tool_calls.append(
                ToolCallPart(new_call_id(), fc.name, dict(fc.args or {}))
            )

        text = ""
        try:
            text = response.text or ""
        except Exception:  # response.text raises if only function calls present
            text = ""

        return ProviderResponse(
            text=text, tool_calls=tool_calls, usage=usage, raw=response
        )
