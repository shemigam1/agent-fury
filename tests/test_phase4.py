import json
import subprocess
from pathlib import Path

import pytest

from fury.evals.harness import RunResult, Task, load_tasks, workspace
from fury.evals.report import aggregate, to_markdown, write_reports
from fury.evals.scorer import score


def test_load_tasks_yaml(tmp_path):
    pytest.importorskip("yaml")
    f = tmp_path / "t.yaml"
    f.write_text(
        "tasks:\n"
        "  - id: a\n    prompt: do a\n    verify: 'true'\n"
        "  - id: b\n    prompt: do b\n    verify: 'false'\n    timeout: 30\n"
    )
    tasks = load_tasks(str(f))
    assert [t.id for t in tasks] == ["a", "b"]
    assert tasks[1].timeout == 30


def test_load_tasks_json(tmp_path):
    f = tmp_path / "t.json"
    f.write_text(json.dumps({"tasks": [{"id": "x", "prompt": "p", "verify": "true"}]}))
    assert load_tasks(str(f))[0].id == "x"


def test_scorer_pass_fail(tmp_path):
    ok, _ = score(str(tmp_path), "true")
    bad, _ = score(str(tmp_path), "false")
    assert ok is True and bad is False


def test_workspace_git_is_isolated(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("orig\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], cwd=repo, check=True)
    with workspace(str(repo)) as ws:
        assert (Path(ws) / "a.txt").is_file()
        (Path(ws) / "b.txt").write_text("scratch\n")  # mutate the copy
    # original repo working tree untouched
    assert not (repo / "b.txt").exists()


def test_workspace_non_git_copy(tmp_path):
    repo = tmp_path / "plain"
    repo.mkdir()
    (repo / "f.py").write_text("x = 1\n")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "junk").write_text("y\n")
    with workspace(str(repo)) as ws:
        assert (Path(ws) / "f.py").is_file()
        assert not (Path(ws) / "node_modules").exists()  # vendor dir filtered


def _results():
    return [
        RunResult("gemini:flash", "t1", True, 3, 100, 20, 0.001, 2.0, 5, 0),
        RunResult("gemini:flash", "t2", False, 5, 200, 40, 0.002, 4.0, 8, 2),
        RunResult("openai:gpt-4o-mini", "t1", True, 2, 90, 15, 0.003, 1.5, 4, 0),
        RunResult("openai:gpt-4o-mini", "t2", True, 4, 150, 30, 0.004, 3.0, 6, 1),
    ]


def test_aggregate_and_ranking():
    stats = aggregate(_results())
    # openai passed 2/2 -> ranked first over gemini 1/2
    assert stats[0].model == "openai:gpt-4o-mini"
    assert stats[0].success_rate == 1.0
    g = next(s for s in stats if s.model == "gemini:flash")
    assert g.success_rate == 0.5
    assert g.tool_error_rate == 2 / 13


def test_write_reports(tmp_path):
    results = _results()
    stats = aggregate(results)
    md = tmp_path / "report.md"
    out_json = write_reports(stats, results, str(md))
    assert md.is_file() and Path(out_json).is_file()
    text = md.read_text()
    assert "reliability leaderboard" in text
    data = json.loads(Path(out_json).read_text())
    assert len(data["leaderboard"]) == 2 and len(data["runs"]) == 4


def test_dashboards_valid():
    base = Path(__import__("fury.obs", fromlist=["x"]).__file__).parent / "deploy" / "grafana" / "dashboards"
    for name in ["agent-overview.json", "evals.json"]:
        json.loads((base / name).read_text())
