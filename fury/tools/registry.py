"""Per-mode tool sets."""

from __future__ import annotations

from fury.tools.base import Tool
from fury.tools.filesystem import list_files_tool, read_file_tool, write_file_tool
from fury.tools.shell import run_shell_tool
from fury.tools.web import web_fetch_tool, web_search_tool

# Base coding tool set, shared by `code` and `auto` modes.
_CODE_TOOLS = [list_files_tool, read_file_tool, write_file_tool, run_shell_tool]

# `assistant` mode swaps in web access on top of read/inspect abilities.
_ASSISTANT_TOOLS = [
    list_files_tool,
    read_file_tool,
    write_file_tool,
    run_shell_tool,
    web_search_tool,
    web_fetch_tool,
]

_BY_MODE = {
    "code": _CODE_TOOLS,
    "auto": _CODE_TOOLS,
    "assistant": _ASSISTANT_TOOLS,
}


def build_registry(mode: str) -> dict[str, Tool]:
    tools = _BY_MODE.get(mode, _CODE_TOOLS)
    return {t.name: t for t in tools}
