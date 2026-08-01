"""Codebase search: glob (find files) and grep (find content)."""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess

from fury.tools._walk import IgnoreSpec, walk_files
from fury.tools.base import Tool, ToolContext, ToolResult

GLOB_LIMIT = 300
GREP_LIMIT = 200


def _glob(ctx: ToolContext, args: dict) -> ToolResult:
    pattern = args["pattern"]
    subdir = args.get("path", ".")
    ctx.resolve(subdir)  # containment check
    matches = []
    for rel in walk_files(ctx.root, subdir):
        # support both "**/*.py" style and bare "*.py" (match on basename too)
        base = rel.rsplit("/", 1)[-1]
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(base, pattern):
            matches.append(rel)
            if len(matches) >= GLOB_LIMIT:
                matches.append(f"… (truncated at {GLOB_LIMIT})")
                break
    if not matches:
        return ToolResult(f'No files match "{pattern}".')
    return ToolResult("\n".join(sorted(matches)))


def _grep_ripgrep(ctx: ToolContext, pattern: str, subdir: str, glob: str | None,
                  ignore_case: bool) -> ToolResult | None:
    rg = shutil.which("rg")
    if not rg:
        return None
    cmd = [rg, "--line-number", "--no-heading", "--color", "never", "-m", "5"]
    if ignore_case:
        cmd.append("-i")
    if glob:
        cmd += ["-g", glob]
    cmd += [pattern, subdir or "."]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=ctx.root
        )
    except subprocess.TimeoutExpired:
        return ToolResult("Error: grep timed out", is_error=True)
    lines = (proc.stdout or "").splitlines()
    if not lines and proc.returncode not in (0, 1):
        return ToolResult(f"Error: {proc.stderr.strip()}", is_error=True)
    if not lines:
        return ToolResult(f'No matches for "{pattern}".')
    if len(lines) > GREP_LIMIT:
        lines = lines[:GREP_LIMIT] + [f"… (truncated at {GREP_LIMIT} matches)"]
    return ToolResult("\n".join(lines))


def _grep_python(ctx: ToolContext, pattern: str, subdir: str, glob: str | None,
                 ignore_case: bool) -> ToolResult:
    flags = re.IGNORECASE if ignore_case else 0
    try:
        rx = re.compile(pattern, flags)
    except re.error as e:
        return ToolResult(f"Error: invalid regex: {e}", is_error=True)
    ignores = IgnoreSpec.load(ctx.root)
    hits: list[str] = []
    for rel in walk_files(ctx.root, subdir, ignores):
        if glob and not fnmatch.fnmatch(rel, glob) and not fnmatch.fnmatch(
            rel.rsplit("/", 1)[-1], glob
        ):
            continue
        path = os.path.join(ctx.root, rel)
        try:
            with open(path, "r", encoding="utf-8", errors="strict") as f:
                for n, line in enumerate(f, 1):
                    if rx.search(line):
                        hits.append(f"{rel}:{n}:{line.rstrip()}")
                        if len(hits) >= GREP_LIMIT:
                            hits.append(f"… (truncated at {GREP_LIMIT} matches)")
                            return ToolResult("\n".join(hits))
        except (UnicodeDecodeError, OSError):
            continue  # skip binary/unreadable files
    if not hits:
        return ToolResult(f'No matches for "{pattern}".')
    return ToolResult("\n".join(hits))


def _grep(ctx: ToolContext, args: dict) -> ToolResult:
    pattern = args["pattern"]
    subdir = args.get("path", ".")
    ctx.resolve(subdir)
    glob = args.get("glob")
    ignore_case = bool(args.get("ignore_case", False))
    # Prefer ripgrep (fast, correct .gitignore + binary handling); fall back to py.
    result = _grep_ripgrep(ctx, pattern, subdir, glob, ignore_case)
    if result is not None:
        return result
    return _grep_python(ctx, pattern, subdir, glob, ignore_case)


glob_tool = Tool(
    name="glob",
    description=(
        "Find files by name/glob pattern (e.g. '**/*.ts', 'test_*.py'). Skips "
        "vendor/build dirs and gitignored paths. Returns matching paths."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern to match paths."},
            "path": {"type": "string", "description": "Sub-directory to search (default '.')."},
        },
        "required": ["pattern"],
    },
    handler=_glob,
)

grep_tool = Tool(
    name="grep",
    description=(
        "Search file contents by regular expression (ripgrep-backed). Returns "
        "path:line:match. Use `glob` to restrict to certain files. Great for "
        "locating symbols across a large codebase."
    ),
    parameters={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regular expression to search for."},
            "path": {"type": "string", "description": "Sub-directory to search (default '.')."},
            "glob": {"type": "string", "description": "Only search files matching this glob (e.g. '*.go')."},
            "ignore_case": {"type": "boolean", "description": "Case-insensitive search."},
        },
        "required": ["pattern"],
    },
    handler=_grep,
)
