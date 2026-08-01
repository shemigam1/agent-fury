"""Aggregate run results into a per-model reliability leaderboard."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from rich.table import Table

from fury.evals.harness import RunResult


@dataclass
class ModelStats:
    model: str
    tasks: int = 0
    passed: int = 0
    iterations: int = 0
    tokens: int = 0
    cost: float = 0.0
    duration: float = 0.0
    tool_calls: int = 0
    tool_errors: int = 0
    task_ids: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.passed / self.tasks if self.tasks else 0.0

    @property
    def avg_iters(self) -> float:
        return self.iterations / self.tasks if self.tasks else 0.0

    @property
    def avg_duration(self) -> float:
        return self.duration / self.tasks if self.tasks else 0.0

    @property
    def tool_error_rate(self) -> float:
        return self.tool_errors / self.tool_calls if self.tool_calls else 0.0


def aggregate(results: list[RunResult]) -> list[ModelStats]:
    by_model: dict[str, ModelStats] = {}
    for r in results:
        s = by_model.setdefault(r.model, ModelStats(model=r.model))
        s.tasks += 1
        s.passed += int(r.passed)
        s.iterations += r.iterations
        s.tokens += r.total_tokens
        s.cost += r.cost
        s.duration += r.duration_s
        s.tool_calls += r.tool_calls
        s.tool_errors += r.tool_errors
    # Rank: highest success rate, then cheapest.
    return sorted(by_model.values(), key=lambda s: (-s.success_rate, s.cost))


def print_table(con, stats: list[ModelStats]) -> None:
    table = Table(title="agent-fury · reliability leaderboard", title_style="bold")
    table.add_column("model", style="cyan")
    table.add_column("pass", justify="right")
    table.add_column("success", justify="right")
    table.add_column("avg iters", justify="right")
    table.add_column("tokens", justify="right")
    table.add_column("cost $", justify="right")
    table.add_column("avg s", justify="right")
    table.add_column("tool err", justify="right")
    for s in stats:
        table.add_row(
            s.model, f"{s.passed}/{s.tasks}", f"{s.success_rate:.0%}",
            f"{s.avg_iters:.1f}", f"{s.tokens:,}", f"{s.cost:.4f}",
            f"{s.avg_duration:.1f}", f"{s.tool_error_rate:.0%}",
        )
    con.console.print(table)


def to_markdown(stats: list[ModelStats], results: list[RunResult]) -> str:
    lines = ["# agent-fury — reliability leaderboard", ""]
    lines.append("| model | pass | success | avg iters | tokens | cost $ | avg s | tool err |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for s in stats:
        lines.append(
            f"| `{s.model}` | {s.passed}/{s.tasks} | {s.success_rate:.0%} | "
            f"{s.avg_iters:.1f} | {s.tokens:,} | {s.cost:.4f} | "
            f"{s.avg_duration:.1f} | {s.tool_error_rate:.0%} |"
        )
    lines += ["", "## Per-task results", ""]
    lines.append("| model | task | result | iters | tokens | cost $ | s |")
    lines.append("| --- | --- | :---: | ---: | ---: | ---: | ---: |")
    for r in results:
        mark = "✅" if r.passed else "❌"
        lines.append(
            f"| `{r.model}` | {r.task_id} | {mark} | {r.iterations} | "
            f"{r.total_tokens:,} | {r.cost:.4f} | {r.duration_s:.1f} |"
        )
    return "\n".join(lines) + "\n"


def write_reports(stats: list[ModelStats], results: list[RunResult], out_md: str) -> str:
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(to_markdown(stats, results))
    out_json = out_md.rsplit(".", 1)[0] + ".json"
    payload = {
        "leaderboard": [
            {
                "model": s.model, "tasks": s.tasks, "passed": s.passed,
                "success_rate": round(s.success_rate, 4), "avg_iters": round(s.avg_iters, 2),
                "tokens": s.tokens, "cost_usd": round(s.cost, 6),
                "avg_duration_s": round(s.avg_duration, 2),
                "tool_error_rate": round(s.tool_error_rate, 4),
            }
            for s in stats
        ],
        "runs": [r.__dict__ for r in results],
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return out_json
