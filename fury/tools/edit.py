"""Precise search/replace editing — the scalable alternative to rewriting whole
files (essential for large source files)."""

from __future__ import annotations

import os

from fury.tools.base import Tool, ToolContext, ToolResult


def _edit(ctx: ToolContext, args: dict) -> ToolResult:
    file_path = args["file_path"]
    old = args["old_string"]
    new = args["new_string"]
    replace_all = bool(args.get("replace_all", False))

    target = ctx.resolve(file_path)
    if not os.path.isfile(target):
        return ToolResult(f'Error: file not found: "{file_path}"', is_error=True)
    if old == new:
        return ToolResult("Error: old_string and new_string are identical", is_error=True)

    with open(target, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    count = content.count(old)
    if count == 0:
        return ToolResult(
            f'Error: old_string not found in "{file_path}". It must match exactly '
            "(including whitespace/indentation).",
            is_error=True,
        )
    if count > 1 and not replace_all:
        return ToolResult(
            f"Error: old_string is not unique ({count} occurrences in "
            f'"{file_path}"). Add surrounding context to disambiguate, or set '
            "replace_all=true.",
            is_error=True,
        )

    updated = content.replace(old, new) if replace_all else content.replace(old, new, 1)
    with open(target, "w", encoding="utf-8") as f:
        f.write(updated)
    where = f"{count} occurrences" if replace_all else "1 occurrence"
    return ToolResult(f'Edited "{file_path}" ({where} replaced).')


edit_tool = Tool(
    name="edit_file",
    description=(
        "Replace an exact string in a file with new text. old_string must match "
        "the file exactly (including indentation) and be unique unless "
        "replace_all is set. Prefer this over write_file for changes to existing "
        "files."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "File to edit, relative to the working dir."},
            "old_string": {"type": "string", "description": "Exact text to find."},
            "new_string": {"type": "string", "description": "Text to replace it with."},
            "replace_all": {"type": "boolean", "description": "Replace every occurrence (default false)."},
        },
        "required": ["file_path", "old_string", "new_string"],
    },
    handler=_edit,
    mutating=True,
)
