"""Language-agnostic filesystem tools, sandboxed to the working directory."""

from __future__ import annotations

import os

from fury.tools.base import Tool, ToolContext, ToolResult

READ_CHAR_LIMIT = 40_000

# Directories that are never worth listing/exploring by default.
_IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".next", "target", ".idea", ".gradle",
}


def _list_files(ctx: ToolContext, args: dict) -> ToolResult:
    directory = args.get("directory", ".")
    target = ctx.resolve(directory)
    if not os.path.isdir(target):
        return ToolResult(f'Error: "{directory}" is not a directory', is_error=True)
    entries = []
    for name in sorted(os.listdir(target)):
        path = os.path.join(target, name)
        is_dir = os.path.isdir(path)
        if is_dir and name in _IGNORED_DIRS:
            entries.append(f"- {name}/ (skipped)")
            continue
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        suffix = "/" if is_dir else ""
        entries.append(f"- {name}{suffix}: size={size} bytes, is_dir={is_dir}")
    return ToolResult("\n".join(entries) if entries else "(empty directory)")


def _read_file(ctx: ToolContext, args: dict) -> ToolResult:
    file_path = args["file_path"]
    target = ctx.resolve(file_path)
    if not os.path.isfile(target):
        return ToolResult(
            f'Error: file not found: "{file_path}"', is_error=True
        )

    offset = args.get("offset")
    limit = args.get("limit")
    if offset is not None or limit is not None:
        # Line-range read for large files (1-based offset).
        start = max(int(offset or 1), 1)
        count = int(limit) if limit is not None else 2000
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        chunk = lines[start - 1 : start - 1 + count]
        body = "".join(chunk)
        header = f"[lines {start}-{start + len(chunk) - 1} of {len(lines)}]\n"
        return ToolResult(header + body)

    with open(target, "r", encoding="utf-8", errors="replace") as f:
        data = f.read(READ_CHAR_LIMIT)
    if len(data) >= READ_CHAR_LIMIT:
        data += (
            f'\n[...file "{file_path}" truncated at {READ_CHAR_LIMIT} chars; '
            "use offset/limit to read more]"
        )
    return ToolResult(data)


def _write_file(ctx: ToolContext, args: dict) -> ToolResult:
    file_path = args["file_path"]
    content = args["content"]
    target = ctx.resolve(file_path)
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return ToolResult(
        f'Wrote "{file_path}" ({len(content)} chars).'
    )


list_files_tool = Tool(
    name="list_files",
    description=(
        "List files and directories (with sizes) at a path relative to the "
        "working directory. Common vendor/build dirs are skipped. Use '.' for "
        "the repo root."
    ),
    parameters={
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory relative to the working dir. Defaults to '.'.",
            }
        },
    },
    handler=_list_files,
)

read_file_tool = Tool(
    name="read_file",
    description=f"Read a UTF-8 text file (up to {READ_CHAR_LIMIT} chars).",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "File to read, relative to the working directory.",
            },
            "offset": {
                "type": "integer",
                "description": "1-based start line for a partial read of a large file.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of lines to read from offset.",
            },
        },
        "required": ["file_path"],
    },
    handler=_read_file,
)

write_file_tool = Tool(
    name="write_file",
    description=(
        "Create or overwrite a file with the given content. Parent directories "
        "are created as needed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "File to write, relative to the working directory.",
            },
            "content": {
                "type": "string",
                "description": "Full content to write into the file.",
            },
        },
        "required": ["file_path", "content"],
    },
    handler=_write_file,
    mutating=True,
)
