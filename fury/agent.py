"""The core agent loop: iterate LLM turns, executing tool calls until done.

Generalizes the original single-file loop into a provider-agnostic, mode-aware,
permission-aware engine. In autonomous (`auto`) mode it first runs a planner pass,
then executes the plan without pausing for the user.
"""

from __future__ import annotations

import time

from fury.console import FuryConsole
from fury.core.context import prune_history
from fury.core.errors import FuryError
from fury.core.history import History, TextPart, ToolCallPart, ToolResultPart
from fury.modes import PLANNER_PROMPT
from fury.session import Session


class Agent:
    def __init__(self, session: Session, console: FuryConsole) -> None:
        self.session = session
        self.console = console

    def run_turn(self, user_prompt: str) -> str:
        """Handle one user prompt to completion; returns the final answer text."""
        s = self.session
        if s.mode.autonomous:
            plan = self._plan(user_prompt)
            s.history.add_user(f"{user_prompt}\n\nFollow this plan:\n{plan}")
        else:
            s.history.add_user(user_prompt)

        try:
            return self._loop()
        except FuryError as e:
            self.console.error(str(e))
            return ""

    # -- autonomous planning stage -----------------------------------------
    def _plan(self, goal: str) -> str:
        s = self.session
        listing = ""
        lf = s.tools.get("list_files")
        if lf is not None:
            listing = lf.run(s.tool_ctx, {"directory": "."}).output
        scratch = History()
        scratch.add_user(f"Goal: {goal}\n\nRepository root:\n{listing}")
        with self.console.thinking("planning"):
            resp = s.provider.generate(PLANNER_PROMPT, scratch, [])
        s.record_usage(resp.usage)
        plan = resp.text.strip() or "(no plan produced)"
        self.console.rule("plan")
        self.console.assistant(plan)
        self.console.rule()
        return plan

    # -- main loop ----------------------------------------------------------
    def _loop(self) -> str:
        s = self.session
        for _ in range(s.config.max_iters):
            s.iterations += 1
            elided = prune_history(s.history, s.context_budget())
            if elided and s.config.verbose:
                self.console.info(f"pruned {elided} old tool output(s) to fit context")

            meta = s.provider.meta
            start = time.perf_counter()
            with s.telemetry.llm_span(meta.system, meta.model, s.mode.name) as span:
                with self.console.thinking(meta.spec):
                    resp = s.provider.generate(
                        s.mode.system_prompt, s.history, s.tool_list
                    )
                cost = s.provider.cost(resp.usage)
                s.telemetry.record_llm(
                    span, meta.system, meta.model, s.mode.name,
                    resp.usage, cost, time.perf_counter() - start,
                )
            s.record_usage(resp.usage)

            parts: list = []
            if resp.text:
                parts.append(TextPart(resp.text))
            parts.extend(resp.tool_calls)
            s.history.add_assistant(parts)

            if resp.text:
                self.console.assistant(resp.text)

            if not resp.tool_calls:
                return resp.text

            results = [self._exec(call) for call in resp.tool_calls]
            s.history.add_tool_results(results)

        self.console.warn(f"Stopped after {s.config.max_iters} iterations.")
        return s.history.last_assistant_text()

    def _exec(self, call: ToolCallPart) -> ToolResultPart:
        s = self.session
        self.console.tool_call(call)
        tool = s.tools.get(call.name)
        if tool is None:
            return ToolResultPart(
                call.id, call.name, f"Unknown tool: {call.name}", is_error=True
            )

        if tool.mutating:
            if s.config.plan_only:
                return ToolResultPart(
                    call.id, call.name,
                    "Refused: fury is in plan-only (read-only) mode.", is_error=True,
                )
            # Autonomous mode and --yolo skip the prompt; interactive coding/assistant
            # modes ask before any mutating/exec action.
            if not s.config.yolo and not s.mode.autonomous:
                if not self.console.ask_permission(call):
                    return ToolResultPart(
                        call.id, call.name, "Denied by user.", is_error=True
                    )

        start = time.perf_counter()
        with s.telemetry.tool_span(call.name) as span:
            result = tool.run(s.tool_ctx, call.args)
            span.set_attribute("fury.tool.error", bool(result.is_error))
        s.tool_calls += 1
        if result.is_error:
            s.tool_errors += 1
        s.telemetry.record_tool(call.name, result.is_error, time.perf_counter() - start)
        part = ToolResultPart(call.id, call.name, result.output, result.is_error)
        self.console.tool_result(part, verbose=s.config.verbose)
        return part
