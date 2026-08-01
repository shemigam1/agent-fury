import os

import pytest

from fury.tools.base import ToolContext
from fury.tools.filesystem import list_files_tool, read_file_tool, write_file_tool


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "hello.txt").write_text("hi there")
    (tmp_path / "sub").mkdir()
    return ToolContext(root=str(tmp_path))


def test_resolve_allows_inside(ctx):
    assert ctx.resolve("hello.txt").endswith("hello.txt")
    assert ctx.resolve(".") == os.path.abspath(ctx.root)


def test_resolve_blocks_escape(ctx):
    with pytest.raises(ValueError):
        ctx.resolve("../etc/passwd")
    with pytest.raises(ValueError):
        ctx.resolve("/etc/passwd")


def test_read_file(ctx):
    res = read_file_tool.run(ctx, {"file_path": "hello.txt"})
    assert not res.is_error
    assert "hi there" in res.output


def test_read_missing_is_error(ctx):
    res = read_file_tool.run(ctx, {"file_path": "nope.txt"})
    assert res.is_error


def test_write_then_list(ctx):
    res = write_file_tool.run(ctx, {"file_path": "sub/new.py", "content": "x = 1\n"})
    assert not res.is_error
    assert os.path.isfile(os.path.join(ctx.root, "sub", "new.py"))
    listing = list_files_tool.run(ctx, {"directory": "sub"})
    assert "new.py" in listing.output


def test_write_escape_blocked(ctx):
    res = write_file_tool.run(ctx, {"file_path": "../evil.txt", "content": "x"})
    assert res.is_error
