"""Per-mode tool sets."""

from __future__ import annotations

from fury.tools.base import Tool
from fury.tools.edit import edit_tool
from fury.tools.filesystem import list_files_tool, read_file_tool, write_file_tool
from fury.tools.repomap import repomap_tool
from fury.tools.search import glob_tool, grep_tool
from fury.tools.shell import run_shell_tool
from fury.tools.web import web_fetch_tool, web_search_tool

# Full coding tool set, shared by `code` and `auto` modes.
_CODE_TOOLS = [
    list_files_tool,
    read_file_tool,
    glob_tool,
    grep_tool,
    repomap_tool,
    write_file_tool,
    edit_tool,
    run_shell_tool,
]

# `assistant` mode: inspect + search the repo, run commands, and reach the web.
_ASSISTANT_TOOLS = [
    list_files_tool,
    read_file_tool,
    glob_tool,
    grep_tool,
    repomap_tool,
    write_file_tool,
    edit_tool,
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
