"""Rich-powered terminal UI for the interactive agent."""

from __future__ import annotations

import json

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text

from fury.core.history import ToolCallPart, ToolResultPart

_BANNER = r"""[bold red]
   __                    ____
  / _|_   _ _ __ _   _  / / /
 | |_| | | | '__| | | |/ / /
 |  _| |_| | |  | |_| /_/_/
 |_|  \__,_|_|   \__, (_|_)
                 |___/       [/bold red][dim]agent-fury[/dim]"""


class FuryConsole:
    def __init__(self) -> None:
        self.console = Console()

    # -- lifecycle ----------------------------------------------------------
    def banner(self, model_spec: str, mode: str, root: str) -> None:
        self.console.print(_BANNER)
        self.console.print(
            f"  [dim]model[/dim] [cyan]{model_spec}[/cyan]   "
            f"[dim]mode[/dim] [magenta]{mode}[/magenta]   "
            f"[dim]dir[/dim] {root}"
        )
        self.console.print()
        guide = [
            ("just type a request", "the agent reads/edits files & runs commands"),
            ("/model <spec>", "switch LLM — keeps the conversation context"),
            ("/mode <code|auto|assistant>", "collaborate · autonomous · general help"),
            ("/cost", "tokens used & estimated cost so far"),
            ("/help", "all commands"),
            ("exit", "quit"),
        ]
        for cmd, desc in guide:
            self.console.print(f"  [cyan]{cmd:<28}[/cyan] [dim]{desc}[/dim]")
        self.console.print()

    def rule(self, label: str = "") -> None:
        self.console.rule(f"[dim]{label}[/dim]" if label else "")

    # -- messages -----------------------------------------------------------
    def info(self, msg: str) -> None:
        self.console.print(f"[dim]{msg}[/dim]")

    def warn(self, msg: str) -> None:
        self.console.print(f"[yellow]! {msg}[/yellow]")

    def error(self, msg: str) -> None:
        self.console.print(f"[bold red]✗ {msg}[/bold red]")

    def assistant(self, text: str) -> None:
        if text.strip():
            self.console.print(Markdown(text))

    def thinking(self, label: str = "thinking"):
        return self.console.status(f"[dim]{label}…[/dim]", spinner="dots")

    # -- tool calls ---------------------------------------------------------
    def tool_call(self, call: ToolCallPart) -> None:
        detail = self._summarize_args(call.name, call.args)
        self.console.print(
            Text.assemble(
                ("  ⚙ ", "bold cyan"),
                (call.name, "bold"),
                (f"  {detail}" if detail else "", "dim"),
            )
        )

    def tool_result(self, result: ToolResultPart, verbose: bool = False) -> None:
        body = result.output.strip()
        if not verbose and len(body) > 500:
            body = body[:500] + f"\n… (+{len(result.output) - 500} chars)"
        style = "red" if result.is_error else "green"
        glyph = "✗" if result.is_error else "✓"
        self.console.print(
            Panel(
                body or "(no output)",
                border_style=style,
                title=f"[{style}]{glyph} {result.name}[/{style}]",
                title_align="left",
                padding=(0, 1),
            )
        )

    def _summarize_args(self, name: str, args: dict) -> str:
        if name == "run_shell":
            return f"$ {args.get('command', '')}"
        if name in ("read_file", "write_file", "edit_file"):
            return str(args.get("file_path", ""))
        if name == "list_files":
            return str(args.get("directory", "."))
        if name in ("glob", "grep"):
            pat = args.get("pattern", "")
            g = args.get("glob")
            return f"{pat}" + (f" in {g}" if g else "")
        if name == "repomap":
            return str(args.get("path", "."))
        if name in ("web_search",):
            return str(args.get("query", ""))
        if name in ("web_fetch",):
            return str(args.get("url", ""))
        try:
            s = json.dumps(args)
        except TypeError:
            s = str(args)
        return s if len(s) < 80 else s[:77] + "…"

    # -- permissions --------------------------------------------------------
    def ask_permission(self, call: ToolCallPart) -> bool:
        detail = self._summarize_args(call.name, call.args)
        self.console.print(
            f"[yellow]Permission needed[/yellow] to run "
            f"[bold]{call.name}[/bold] [dim]{detail}[/dim]"
        )
        return Confirm.ask("  Allow?", default=True, console=self.console)

    # -- status -------------------------------------------------------------
    def cost_line(self, in_tok: int, out_tok: int, cost: float) -> None:
        self.console.print(
            f"[dim]tokens in {in_tok:,} · out {out_tok:,} · ~${cost:.4f}[/dim]"
        )
