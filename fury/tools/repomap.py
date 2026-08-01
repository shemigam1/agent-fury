"""A compact, ranked repository map.

Gives the model a birds-eye outline of a large codebase — files ranked by how
many top-level definitions they contain, each with its key symbols — without
reading every file. Language-agnostic via per-extension regexes (no tree-sitter
dependency).
"""

from __future__ import annotations

import os
import re

from fury.tools._walk import walk_files
from fury.tools.base import Tool, ToolContext, ToolResult

# extension -> list of (regex, label) capturing a symbol name in group 1.
_PATTERNS: dict[str, list[re.Pattern]] = {
    ext: [re.compile(p, re.MULTILINE) for p in pats]
    for exts, pats in [
        ((".py",), [r"^\s*class\s+(\w+)", r"^\s*(?:async\s+)?def\s+(\w+)"]),
        ((".js", ".jsx", ".mjs", ".ts", ".tsx"),
         [r"(?:export\s+)?class\s+(\w+)", r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
          r"(?:export\s+)?const\s+(\w+)\s*="]),
        ((".go",), [r"^func\s+(?:\([^)]*\)\s*)?(\w+)", r"^type\s+(\w+)"]),
        ((".rs",), [r"^\s*(?:pub\s+)?fn\s+(\w+)", r"^\s*(?:pub\s+)?struct\s+(\w+)",
                    r"^\s*(?:pub\s+)?enum\s+(\w+)", r"^\s*(?:pub\s+)?trait\s+(\w+)"]),
        ((".rb",), [r"^\s*class\s+(\w+)", r"^\s*def\s+(\w+)"]),
        ((".java", ".kt"),
         [r"(?:public|private|protected)?\s*(?:class|interface|enum)\s+(\w+)"]),
        ((".c", ".h", ".cpp", ".cc", ".hpp"),
         [r"^\w[\w\s\*]+\s+(\w+)\s*\([^;]*\)\s*\{"]),
    ]
    for ext in exts
}

_PER_FILE = 12
_DEFAULT_MAX_FILES = 40


def _symbols(path: str, ext: str) -> list[str]:
    pats = _PATTERNS.get(ext)
    if not pats:
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="strict") as f:
            text = f.read(200_000)
    except (UnicodeDecodeError, OSError):
        return []
    found: list[str] = []
    seen: set[str] = set()
    for rx in pats:
        for m in rx.finditer(text):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                found.append(name)
    return found


def _repomap(ctx: ToolContext, args: dict) -> ToolResult:
    subdir = args.get("path", ".")
    ctx.resolve(subdir)
    max_files = int(args.get("max_files", _DEFAULT_MAX_FILES))

    ranked: list[tuple[int, str, list[str]]] = []
    total_files = 0
    for rel in walk_files(ctx.root, subdir):
        total_files += 1
        ext = os.path.splitext(rel)[1]
        syms = _symbols(os.path.join(ctx.root, rel), ext)
        if syms:
            ranked.append((len(syms), rel, syms))

    ranked.sort(key=lambda t: (-t[0], t[1]))
    shown = ranked[:max_files]

    lines = [f"Repo map ({len(ranked)} code files with symbols / {total_files} files):"]
    for _, rel, syms in shown:
        lines.append(rel)
        for s in syms[:_PER_FILE]:
            lines.append(f"  {s}")
        if len(syms) > _PER_FILE:
            lines.append(f"  … (+{len(syms) - _PER_FILE} more)")
    if len(ranked) > max_files:
        lines.append(f"… (+{len(ranked) - max_files} more files; raise max_files)")
    return ToolResult("\n".join(lines))


repomap_tool = Tool(
    name="repomap",
    description=(
        "Produce a ranked outline of the repository: the most definition-dense "
        "files and their top-level symbols (classes/functions/types). Call this "
        "first to orient yourself in an unfamiliar or large codebase."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Sub-directory to map (default '.')."},
            "max_files": {"type": "integer", "description": f"Max files to list (default {_DEFAULT_MAX_FILES})."},
        },
    },
    handler=_repomap,
)
