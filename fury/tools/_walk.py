"""Shared filesystem walking with .gitignore awareness.

Used by glob/grep/repomap so they all skip vendor/build dirs and gitignored
paths consistently. The gitignore matcher is intentionally lightweight (root
.gitignore, common pattern forms) — ripgrep is preferred for grep where full
gitignore semantics matter.
"""

from __future__ import annotations

import fnmatch
import os

# Directories never worth walking into.
IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", ".next", "target",
    ".idea", ".gradle", ".tox", "coverage", ".cache", "vendor",
}


class IgnoreSpec:
    """A minimal .gitignore matcher (root file only, common patterns)."""

    def __init__(self, patterns: list[str]) -> None:
        self.patterns = patterns

    @classmethod
    def load(cls, root: str) -> "IgnoreSpec":
        patterns: list[str] = []
        gi = os.path.join(root, ".gitignore")
        if os.path.isfile(gi):
            with open(gi, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("!"):
                        patterns.append(line.rstrip("/"))
        return cls(patterns)

    def matches(self, rel_path: str) -> bool:
        rel_path = rel_path.replace(os.sep, "/")
        base = rel_path.rsplit("/", 1)[-1]
        for pat in self.patterns:
            anchored = pat.startswith("/")
            p = pat.lstrip("/")
            if anchored:
                if fnmatch.fnmatch(rel_path, p) or rel_path == p:
                    return True
            else:
                if fnmatch.fnmatch(base, p) or fnmatch.fnmatch(rel_path, p):
                    return True
                # match a directory component anywhere in the path
                if p in rel_path.split("/"):
                    return True
        return False


def walk_files(root: str, subdir: str = ".", ignores: IgnoreSpec | None = None):
    """Yield file paths (relative to ``root``) under ``subdir``, skipping
    ignored directories and gitignored paths."""
    ignores = ignores if ignores is not None else IgnoreSpec.load(root)
    start = os.path.abspath(os.path.join(root, subdir))
    for dirpath, dirnames, filenames in os.walk(start):
        rel_dir = os.path.relpath(dirpath, root)
        # prune ignored / vendor dirs in place so os.walk skips them
        kept = []
        for d in dirnames:
            if d in IGNORED_DIRS:
                continue
            rel = os.path.normpath(os.path.join(rel_dir, d)) if rel_dir != "." else d
            if ignores.matches(rel):
                continue
            kept.append(d)
        dirnames[:] = kept
        for name in filenames:
            rel = os.path.normpath(os.path.join(rel_dir, name)) if rel_dir != "." else name
            if ignores.matches(rel):
                continue
            yield rel.replace(os.sep, "/")
