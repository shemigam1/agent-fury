"""Pass/fail scoring via a task's verification command.

Language-agnostic by construction: the signal is simply the exit code of an
arbitrary shell command (`pytest -q`, `go test ./...`, `npm test`, `make check`,
`grep -q ...`), run inside the isolated workspace.
"""

from __future__ import annotations

import subprocess


def score(workdir: str, verify: str, timeout: int = 300) -> tuple[bool, str]:
    """Run the verify command; return (passed, tail-of-output)."""
    try:
        proc = subprocess.run(
            verify, shell=True, cwd=workdir,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"verify timed out after {timeout}s"
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output[-800:]
