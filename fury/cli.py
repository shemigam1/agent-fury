"""Command-line entry point: subcommands + interactive REPL."""

from __future__ import annotations

import argparse
import sys

from fury import __version__
from fury.agent import Agent
from fury.config import Config
from fury.console import FuryConsole
from fury.core.errors import FuryError
from fury.modes import MODES
from fury.providers.registry import KNOWN_PROVIDERS
from fury.session import Session

_HELP = """[bold]Slash commands[/bold]
  [cyan]/model[/cyan] <provider:model>   switch LLM (keeps full context)
  [cyan]/mode[/cyan] <code|auto|assistant>  switch agent mode
  [cyan]/models[/cyan]                   list providers & which keys are set
  [cyan]/tools[/cyan]                    list tools available in this mode
  [cyan]/cost[/cyan]                     session token usage & est. cost
  [cyan]/clear[/cyan]                    reset the conversation
  [cyan]/cwd[/cyan]                      show the working directory
  [cyan]/help[/cyan]                     this help
  [cyan]/exit[/cyan]                     quit (or just type `exit` / `quit`)
"""


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dir", dest="working_dir", help="working directory (default: cwd)")
    p.add_argument("--model", dest="model_spec", help="model spec, e.g. gemini:flash")
    p.add_argument("--mode", choices=list(MODES), help="agent mode")
    p.add_argument("--yolo", action="store_true", default=None,
                   help="auto-approve mutating tools (no prompts)")
    p.add_argument("--plan-only", dest="plan_only", action="store_true", default=None,
                   help="read-only: refuse writes/shell")
    p.add_argument("--verbose", action="store_true", default=None,
                   help="show full tool output")
    p.add_argument("--max-iters", dest="max_iters", type=int, help="max agent iterations")
    p.add_argument("--telemetry", action="store_true", default=None,
                   help="export OpenTelemetry traces/metrics (needs `fury obs up`)")


def _parse(argv):
    parser = argparse.ArgumentParser(prog="fury", description="agent-fury — multi-provider coding agent")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    _add_common(parser)
    sub = parser.add_subparsers(dest="command")

    _add_common(sub.add_parser("chat", help="interactive REPL (default)"))
    run_p = sub.add_parser("run", help="one-shot: run a single prompt and exit")
    _add_common(run_p)
    run_p.add_argument("prompt", nargs="+", help="the prompt")
    _add_common(sub.add_parser("models", help="list providers and configured keys"))
    _add_common(sub.add_parser("config", help="show resolved configuration"))
    obs_p = sub.add_parser("obs", help="manage the observability stack (docker)")
    obs_p.add_argument("action", choices=["up", "down", "status"], help="stack action")

    ev = sub.add_parser("evals", help="run the eval suite and print a leaderboard")
    ev.add_argument("--repo", default=".", help="target repo to run tasks against")
    ev.add_argument("--tasks", required=True, help="path to a task file (.yaml/.json)")
    ev.add_argument("--models", help="comma-separated model specs (default: config model)")
    ev.add_argument("--out", default="fury-eval-report.md", help="markdown report path")
    ev.add_argument("--telemetry", action="store_true", default=None,
                    help="export eval metrics to the observability stack")
    return parser.parse_args(argv)


def _config_from(args) -> Config:
    return Config.load(
        working_dir=getattr(args, "working_dir", None),
        model_spec=getattr(args, "model_spec", None),
        mode=getattr(args, "mode", None),
        yolo=getattr(args, "yolo", None),
        plan_only=getattr(args, "plan_only", None),
        verbose=getattr(args, "verbose", None),
        max_iters=getattr(args, "max_iters", None),
        telemetry=getattr(args, "telemetry", None),
    )


def _make_session(config: Config, con: FuryConsole) -> Session | None:
    try:
        return Session(config)
    except FuryError as e:
        con.error(str(e))
        con.info("Tip: run `fury models` to see which API keys are set.")
        return None


# -- subcommands ------------------------------------------------------------
def _cmd_models(config: Config, con: FuryConsole) -> int:
    con.console.print("[bold]Providers[/bold]")
    for name, info in KNOWN_PROVIDERS.items():
        env = info.get("env")
        has = "[green]set[/green]" if config.key(name) else (
            "[dim]n/a (local)[/dim]" if env is None else "[red]missing[/red]"
        )
        env_label = f"[dim]${env}[/dim]" if env else "[dim]—[/dim]"
        con.console.print(f"  [cyan]{name:<11}[/cyan] {env_label:<24} key: {has}")
        con.console.print(f"     [dim]e.g. {name}:{info['examples'][0]}[/dim]")
    return 0


def _cmd_config(config: Config, con: FuryConsole) -> int:
    con.console.print(f"[bold]model[/bold]     {config.model_spec}")
    con.console.print(f"[bold]mode[/bold]      {config.mode}")
    con.console.print(f"[bold]dir[/bold]       {config.root}")
    con.console.print(f"[bold]keys[/bold]      {', '.join(config.keys) or '(none)'}")
    con.console.print(f"[bold]max_iters[/bold] {config.max_iters}")
    return 0


def _cmd_run(config: Config, con: FuryConsole, prompt: str) -> int:
    session = _make_session(config, con)
    if session is None:
        return 1
    agent = Agent(session, con)
    try:
        agent.run_turn(prompt)
    finally:
        session.telemetry.shutdown()
    if config.verbose:
        con.cost_line(
            session.total_usage.input_tokens,
            session.total_usage.output_tokens,
            session.total_cost,
        )
    return 0


def _cmd_evals(config: Config, con: FuryConsole, args) -> int:
    from fury.evals import aggregate, load_tasks, print_table, run_suite, write_reports

    models = (
        [m.strip() for m in args.models.split(",")]
        if args.models else [config.model_spec]
    )
    try:
        tasks = load_tasks(args.tasks)
    except (OSError, KeyError, ValueError) as e:
        con.error(f"could not load tasks from {args.tasks}: {e}")
        return 1
    con.info(f"running {len(tasks)} task(s) × {len(models)} model(s) on {args.repo}")
    results = run_suite(
        con, repo=args.repo, tasks=tasks, models=models,
        telemetry_enabled=bool(args.telemetry), endpoint=config.otel_endpoint,
    )
    stats = aggregate(results)
    con.console.print()
    print_table(con, stats)
    out_json = write_reports(stats, results, args.out)
    con.info(f"reports written: {args.out}, {out_json}")
    return 0


def _cmd_obs(con: FuryConsole, action: str) -> int:
    import shutil
    import subprocess
    from importlib.resources import files

    if not shutil.which("docker"):
        con.error("docker not found. Install Docker Desktop to run the stack.")
        return 1
    deploy = files("fury.obs") / "deploy"
    compose = deploy / "docker-compose.yml"
    if not compose.is_file():
        con.error(f"compose file not found at {compose}")
        return 1
    deploy_dir = str(compose.parent)
    cmds = {
        "up": ["docker", "compose", "up", "-d"],
        "down": ["docker", "compose", "down"],
        "status": ["docker", "compose", "ps"],
    }
    con.info(f"docker compose {action} (in {deploy_dir})")
    rc = subprocess.run(cmds[action], cwd=deploy_dir).returncode
    if action == "up" and rc == 0:
        con.console.print(
            "\n[green]stack up[/green] — Grafana [cyan]http://localhost:3000[/cyan] "
            "(dashboard: agent-fury · Overview)\n"
            "Now run with telemetry: [bold]fury --telemetry[/bold]"
        )
    return rc


def _cmd_chat(config: Config, con: FuryConsole) -> int:
    session = _make_session(config, con)
    if session is None:
        return 1
    agent = Agent(session, con)
    con.banner(config.model_spec, config.mode, config.root)
    while True:
        try:
            line = con.console.input("[bold red]fury ›[/bold red] ").strip()
        except (EOFError, KeyboardInterrupt):
            con.console.print()
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break
        if line.startswith("/"):
            if _handle_slash(line, session, con):
                break
            continue
        try:
            agent.run_turn(line)
        except KeyboardInterrupt:
            con.warn("interrupted")
    session.telemetry.shutdown()
    con.info("bye.")
    return 0


def _handle_slash(line: str, session: Session, con: FuryConsole) -> bool:
    """Return True to signal exit."""
    parts = line.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/exit", "/quit"):
        return True
    if cmd == "/help":
        con.console.print(_HELP)
    elif cmd == "/model":
        if not arg:
            con.warn("usage: /model <provider:model>")
        else:
            try:
                session.switch_model(arg)
                con.info(f"switched to {session.provider.meta.spec} (context preserved)")
            except FuryError as e:
                con.error(str(e))
    elif cmd == "/mode":
        if arg not in MODES:
            con.warn(f"usage: /mode <{'|'.join(MODES)}>")
        else:
            session.switch_mode(arg)
            con.info(f"mode: {arg} · tools: {', '.join(session.tools)}")
    elif cmd == "/models":
        _cmd_models(session.config, con)
    elif cmd == "/tools":
        con.info(", ".join(session.tools))
    elif cmd == "/cost":
        con.cost_line(
            session.total_usage.input_tokens,
            session.total_usage.output_tokens,
            session.total_cost,
        )
    elif cmd == "/clear":
        session.history.messages.clear()
        con.info("conversation cleared")
    elif cmd == "/cwd":
        con.info(session.config.root)
    else:
        con.warn(f"unknown command: {cmd} (try /help)")
    return False


def main(argv=None) -> int:
    args = _parse(argv)
    if getattr(args, "version", False):
        print(f"agent-fury {__version__}")
        return 0
    con = FuryConsole()
    config = _config_from(args)
    command = args.command or "chat"
    if command == "models":
        return _cmd_models(config, con)
    if command == "config":
        return _cmd_config(config, con)
    if command == "obs":
        return _cmd_obs(con, args.action)
    if command == "evals":
        return _cmd_evals(config, con, args)
    if command == "run":
        return _cmd_run(config, con, " ".join(args.prompt))
    return _cmd_chat(config, con)


if __name__ == "__main__":
    sys.exit(main())
