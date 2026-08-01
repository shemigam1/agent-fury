"""Token-budget management for the conversation.

Over a long task against a big repo, tool outputs (file reads, greps, shell logs)
accumulate and can overflow the model's context window. This elides the *oldest*
tool outputs first while preserving the recent turns and all user/assistant text,
so the agent keeps working instead of erroring out.
"""

from __future__ import annotations

from fury.core.history import History, TextPart, ToolCallPart, ToolResultPart

_ELIDED_PREFIX = "[elided"


def estimate_tokens(text: str) -> int:
    # Cheap, dependency-free heuristic (~4 chars/token).
    return max(1, len(text) // 4)


def history_tokens(history: History) -> int:
    total = 0
    for msg in history:
        for p in msg.parts:
            if isinstance(p, TextPart):
                total += estimate_tokens(p.text)
            elif isinstance(p, ToolCallPart):
                total += estimate_tokens(str(p.args)) + 5
            elif isinstance(p, ToolResultPart):
                total += estimate_tokens(p.output)
    return total


def prune_history(history: History, max_tokens: int, keep_recent: int = 6) -> int:
    """Elide old tool outputs until under budget. Returns count elided."""
    if history_tokens(history) <= max_tokens:
        return 0
    elided = 0
    n = len(history.messages)
    for i, msg in enumerate(history.messages):
        if n - i <= keep_recent:
            break
        if msg.role == "tool":
            for p in msg.parts:
                if (
                    isinstance(p, ToolResultPart)
                    and not p.output.startswith(_ELIDED_PREFIX)
                    and len(p.output) > 200
                ):
                    p.output = (
                        f"{_ELIDED_PREFIX} {len(p.output)} chars of earlier "
                        f"{p.name} output to save context]"
                    )
                    elided += 1
        if history_tokens(history) <= max_tokens:
            break
    return elided
