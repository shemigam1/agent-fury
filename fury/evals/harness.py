"""The evaluation harness.

For each (model, task) it runs the agent autonomously against an **isolated copy**
of the target repo, then scores the result with the task's verify command. The
target repo is never mutated: git repos get a throwaway `git worktree`, non-git
directories get a filtered copy.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass

from fury.agent import Agent
from fury.config import Config
from fury.console import FuryConsole
from fury.evals.scorer import score
from fury.obs.telemetry import Telemetry
from fury.session import Session
from fury.tools._walk import IGNORED_DIRS


@dataclass
class Task:
    id: str
    prompt: str
    verify: str
    setup: str | None = None
    timeout: int = 300


@dataclass
class RunResult:
    model: str
    task_id: str
    passed: bool
    iterations: int
    input_tokens: int
    output_tokens: int
    cost: float
    duration_s: float
    tool_calls: int
    tool_errors: int
    error: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def load_tasks(path: str) -> list[Task]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if path.endswith((".yaml", ".yml")):
        import yaml
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return [Task(**t) for t in data["tasks"]]


@contextmanager
def workspace(repo: str):
    """Yield an isolated working copy of ``repo`` that is safe to mutate."""
    repo = os.path.abspath(repo)
    is_git = os.path.isdir(os.path.join(repo, ".git"))
    tmp = tempfile.mkdtemp(prefix="fury-eval-")
    wt = os.path.join(tmp, "wt")
    if is_git:
        subprocess.run(
            ["git", "-C", repo, "worktree", "add", "--detach", wt, "HEAD"],
            check=True, capture_output=True, text=True,
        )
        try:
            yield wt
        finally:
            subprocess.run(
                ["git", "-C", repo, "worktree", "remove", "--force", wt],
                capture_output=True,
            )
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        shutil.copytree(repo, wt, ignore=shutil.ignore_patterns(*IGNORED_DIRS))
        try:
            yield wt
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def run_task(
    model: str, task: Task, repo: str, telemetry: Telemetry, con: FuryConsole
) -> RunResult:
    con.rule(f"{model} · {task.id}")
    with workspace(repo) as ws:
        if task.setup:
            subprocess.run(task.setup, shell=True, cwd=ws, capture_output=True)
        config = Config.load(working_dir=ws, model_spec=model, mode="auto", yolo=True)
        # Provider resolution failures (bad key/spec) propagate to run_suite,
        # which records the run as a failure.
        session = Session(config, telemetry=telemetry)
        error = ""
        start = time.perf_counter()
        try:
            Agent(session, con).run_turn(task.prompt)
        except Exception as e:  # noqa: BLE001 - a crashed run is still a failed task
            error = str(e)
        duration = time.perf_counter() - start

        passed, detail = score(ws, task.verify, task.timeout)
        con.info(f"verify → {'PASS' if passed else 'FAIL'}")
        if not passed and detail.strip():
            con.info(detail.strip()[-300:])

    usage = session.total_usage
    result = RunResult(
        model=model, task_id=task.id, passed=passed,
        iterations=session.iterations,
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        cost=session.total_cost, duration_s=duration,
        tool_calls=session.tool_calls, tool_errors=session.tool_errors,
        error=error,
    )
    telemetry.record_eval(model, passed, result.iterations, result.cost, duration)
    return result


def run_suite(
    con: FuryConsole, repo: str, tasks: list[Task], models: list[str],
    telemetry_enabled: bool = False, endpoint: str = "localhost:4317",
) -> list[RunResult]:
    # One shared Telemetry for the whole suite (OTel providers set once).
    telemetry = Telemetry(telemetry_enabled, endpoint)
    results: list[RunResult] = []
    try:
        for model in models:
            for task in tasks:
                try:
                    results.append(run_task(model, task, repo, telemetry, con))
                except Exception as e:  # noqa: BLE001
                    con.error(f"{model}/{task.id}: {e}")
                    results.append(RunResult(model, task.id, False, 0, 0, 0, 0.0, 0.0, 0, 0, str(e)))
    finally:
        telemetry.shutdown()
    return results
