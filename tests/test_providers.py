"""Serialization tests for the provider adapters.

These construct providers with dummy keys (no network is touched at construction
or during serialization) and assert that the *same* canonical history maps into
each provider's native format with consistent tool-call ids — the property that
makes mid-session model switching lossless.
"""

import pytest

from fury.core.history import History, TextPart, ToolCallPart, ToolResultPart
from fury.providers.base import ProviderMeta
from fury.tools.filesystem import read_file_tool


def _sample_history() -> History:
    h = History()
    h.add_user("read a.py")
    h.add_assistant([TextPart("ok"), ToolCallPart("call_9", "read_file", {"file_path": "a.py"})])
    h.add_tool_results([ToolResultPart("call_9", "read_file", "print(1)", False)])
    h.add_user("thanks")
    return h


def test_openai_serialization():
    openai = pytest.importorskip("openai")  # noqa: F841
    from fury.providers.openai_compat import OpenAICompatProvider

    meta = ProviderMeta("openai", "openai", "gpt-4o-mini")
    p = OpenAICompatProvider(meta, api_key="dummy", base_url=None)
    msgs = p._messages("SYS", _sample_history())

    assert msgs[0] == {"role": "system", "content": "SYS"}
    # assistant tool_call id must equal the tool message's tool_call_id
    asst = next(m for m in msgs if m["role"] == "assistant" and m.get("tool_calls"))
    tool = next(m for m in msgs if m["role"] == "tool")
    assert asst["tool_calls"][0]["id"] == tool["tool_call_id"] == "call_9"

    tools = p._tools([read_file_tool])
    assert tools[0]["function"]["name"] == "read_file"


def test_anthropic_serialization():
    anthropic = pytest.importorskip("anthropic")  # noqa: F841
    from fury.providers.anthropic import AnthropicProvider

    meta = ProviderMeta("anthropic", "anthropic", "claude-x")
    p = AnthropicProvider(meta, api_key="dummy")
    msgs = p._messages(_sample_history())

    # tool_use in an assistant msg; tool_result carried in a *user* msg, ids match
    use = next(b for m in msgs if m["role"] == "assistant"
               for b in m["content"] if b["type"] == "tool_use")
    res = next(b for m in msgs if m["role"] == "user" and isinstance(m["content"], list)
               for b in m["content"] if b["type"] == "tool_result")
    assert use["id"] == res["tool_use_id"] == "call_9"


def test_gemini_schema_conversion():
    genai = pytest.importorskip("google.genai")
    from google.genai import types

    from fury.providers.gemini import _to_genai_schema

    schema = _to_genai_schema(types, read_file_tool.parameters)
    assert schema.type == types.Type.OBJECT
    assert "file_path" in schema.properties
    assert schema.required == ["file_path"]


def test_context_preserved_across_providers():
    """The same history serialized to two providers keeps the tool result text."""
    openai = pytest.importorskip("openai")  # noqa: F841
    anthropic = pytest.importorskip("anthropic")  # noqa: F841
    from fury.providers.anthropic import AnthropicProvider
    from fury.providers.openai_compat import OpenAICompatProvider

    hist = _sample_history()
    oai = OpenAICompatProvider(ProviderMeta("openai", "openai", "m"), "d")._messages("S", hist)
    ant = AnthropicProvider(ProviderMeta("anthropic", "anthropic", "m"), "d")._messages(hist)

    assert any("print(1)" in str(m.get("content")) for m in oai)
    assert any("print(1)" in str(m["content"]) for m in ant)
