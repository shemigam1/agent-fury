from fury.core.history import (
    History,
    TextPart,
    ToolCallPart,
    ToolResultPart,
    Usage,
    new_call_id,
)


def test_usage_add():
    a = Usage(10, 5)
    b = Usage(1, 2)
    c = a + b
    assert (c.input_tokens, c.output_tokens, c.total) == (11, 7, 18)


def test_call_ids_unique():
    assert new_call_id() != new_call_id()


def test_history_shape():
    h = History()
    h.add_user("hello")
    call = ToolCallPart("call_1", "read_file", {"file_path": "a.py"})
    h.add_assistant([TextPart("reading"), call])
    h.add_tool_results([ToolResultPart("call_1", "read_file", "contents", False)])

    assert [m.role for m in h] == ["user", "assistant", "tool"]
    assert h.messages[1].tool_calls()[0].name == "read_file"
    assert h.messages[1].text() == "reading"
