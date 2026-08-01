"""Tool primitives.

A ``Tool`` is defined once with a JSON-Schema parameter spec and a plain Python
handler. Provider adapters convert the JSON Schema into their own tool/function
format, so a tool is written once and works across Gemini, OpenAI-compatible and
Anthropic backends.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable


@dataclass
class ToolResult:
    output: str
    is_error: bool = False


@dataclass
class ToolContext:
    """Everything a tool handler is allowed to know about the environment."""

    root: str  # absolute sandbox root; tools may not touch anything outside it

    def resolve(self, rel_path: str) -> str:
        """Resolve a user/model-supplied path *inside* the sandbox.

        Raises ValueError if the path escapes the working directory. This is the
        generalized version of the containment check the original project applied
        per-tool, now rooted at an arbitrary working directory.
        """
        target = os.path.abspath(os.path.join(self.root, rel_path))
        root = os.path.abspath(self.root)
        if target != root and not target.startswith(root + os.sep):
            raise ValueError(
                f'path "{rel_path}" is outside the permitted working directory'
            )
        return target


Handler = Callable[[ToolContext, dict], ToolResult]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema (an object schema)
    handler: Handler
    mutating: bool = False  # True => needs permission / blocked in --plan-only

    def run(self, ctx: ToolContext, args: dict) -> ToolResult:
        try:
            return self.handler(ctx, args)
        except ValueError as e:
            return ToolResult(f"Error: {e}", is_error=True)
        except Exception as e:  # noqa: BLE001 - surfaced back to the model
            return ToolResult(f"Error running {self.name}: {e}", is_error=True)
