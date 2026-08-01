"""Generic, language-agnostic command execution.

The agent inspects the repo itself and decides *what* to run (``npm test``,
``go test ./...``, ``cargo test``, ``pytest``, ``make`` …). Nothing here is tied
to any language or toolchain.
"""

from __future__ import annotations

import subprocess

from fury.tools.base import Tool, ToolContext, ToolResult

SHELL_TIMEOUT = 120  # seconds
OUTPUT_LIMIT = 20_000  # chars of combined stdout/stderr returned to the model


def _run_shell(ctx: ToolContext, args: dict) -> ToolResult:
    command = args["command"]
    # Optional sub-directory to run in, still sandboxed to the working dir.
    cwd = ctx.resolve(args.get("cwd", "."))
    timeout = int(args.get("timeout", SHELL_TIMEOUT))
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            f"Error: command timed out after {timeout}s: {command}", is_error=True
        )

    chunks = []
    if proc.stdout:
        chunks.append(f"STDOUT:\n{proc.stdout}")
    if proc.stderr:
        chunks.append(f"STDERR:\n{proc.stderr}")
    chunks.append(f"(exit code {proc.returncode})")
    out = "\n".join(chunks)
    if len(out) > OUTPUT_LIMIT:
        out = out[:OUTPUT_LIMIT] + "\n[...output truncated]"
    return ToolResult(out, is_error=proc.returncode != 0)


run_shell_tool = Tool(
    name="run_shell",
    description=(
        "Run a shell command inside the working directory and return its stdout, "
        "stderr, and exit code. Use this to build, run tests, inspect git, or run "
        "any tool the project uses. Inspect the repo first to choose the right "
        "command for its language/toolchain."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "cwd": {
                "type": "string",
                "description": "Sub-directory to run in, relative to the working dir. Defaults to '.'.",
            },
            "timeout": {
                "type": "integer",
                "description": f"Max seconds to allow (default {SHELL_TIMEOUT}).",
            },
        },
        "required": ["command"],
    },
    handler=_run_shell,
    mutating=True,
)
