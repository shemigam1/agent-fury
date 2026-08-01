import pytest

from fury.core.context import history_tokens, prune_history
from fury.core.history import History, TextPart, ToolCallPart, ToolResultPart
from fury.tools._walk import IgnoreSpec, walk_files
from fury.tools.base import ToolContext
from fury.tools.edit import edit_tool
from fury.tools.repomap import repomap_tool
from fury.tools.search import glob_tool, grep_tool


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "app.py").write_text("class App:\n    def run(self):\n        pass\n")
    (tmp_path / "util.js").write_text("export function helper() { return 1 }\n")
    (tmp_path / ".gitignore").write_text("ignored.py\nsecret/\n")
    (tmp_path / "ignored.py").write_text("SECRET = 1\n")
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "keys.py").write_text("KEY = 'x'\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("junk\n")
    return ToolContext(root=str(tmp_path))


def test_walk_respects_gitignore_and_vendor(repo):
    files = set(walk_files(repo.root))
    assert "app.py" in files and "util.js" in files
    assert "ignored.py" not in files          # gitignore file pattern
    assert "secret/keys.py" not in files      # gitignore dir pattern
    assert "node_modules/dep.js" not in files  # vendor dir


def test_glob(repo):
    res = glob_tool.run(repo, {"pattern": "*.py"})
    assert "app.py" in res.output
    assert "ignored.py" not in res.output


def test_grep(repo):
    res = grep_tool.run(repo, {"pattern": "class App"})
    assert "app.py:1" in res.output
    # gitignored content should not surface
    res2 = grep_tool.run(repo, {"pattern": "SECRET"})
    assert "ignored.py" not in res2.output


def test_repomap(repo):
    res = repomap_tool.run(repo, {})
    assert "app.py" in res.output
    assert "App" in res.output and "run" in res.output
    assert "helper" in res.output


def test_edit_unique(repo):
    res = edit_tool.run(repo, {"file_path": "app.py", "old_string": "pass", "new_string": "return 42"})
    assert not res.is_error
    assert "return 42" in (repo.resolve("app.py") and open(repo.resolve("app.py")).read())


def test_edit_not_found(repo):
    res = edit_tool.run(repo, {"file_path": "app.py", "old_string": "nonexistent", "new_string": "x"})
    assert res.is_error


def test_edit_ambiguous(repo):
    (repo.resolve("dup.txt"))
    open(repo.resolve("dup.txt"), "w").write("x\nx\n")
    res = edit_tool.run(repo, {"file_path": "dup.txt", "old_string": "x", "new_string": "y"})
    assert res.is_error and "not unique" in res.output
    res2 = edit_tool.run(repo, {"file_path": "dup.txt", "old_string": "x", "new_string": "y", "replace_all": True})
    assert not res2.is_error


def test_prune_history_elides_old_tool_output():
    h = History()
    for i in range(8):
        h.add_user(f"q{i}")
        h.add_assistant([TextPart("ok"), ToolCallPart(f"c{i}", "read_file", {})])
        h.add_tool_results([ToolResultPart(f"c{i}", "read_file", "X" * 4000)])
    before = history_tokens(h)
    elided = prune_history(h, max_tokens=before // 2, keep_recent=4)
    assert elided > 0
    assert history_tokens(h) < before
