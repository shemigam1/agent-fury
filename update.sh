#!/usr/bin/env bash
#
# agent-fury updater — pull the latest without a manual reinstall.
#   curl -fsSL https://raw.githubusercontent.com/shemigam1/agent-fury/main/update.sh | bash
#
# Overridable:
#   FURY_REF=v0.2.1     update to a specific tag/branch (default: latest on main)
#   FURY_EXTRAS=openai  extras to keep when pinning a ref (default: all)
#
set -euo pipefail

REPO="${FURY_REPO:-https://github.com/shemigam1/agent-fury.git}"
EXTRAS="${FURY_EXTRAS:-all}"

info() { printf '\033[36m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

command -v pipx >/dev/null 2>&1 || die "pipx not found — run the install script instead."
pipx list 2>/dev/null | grep -q agent-fury \
  || die "agent-fury isn't installed via pipx — run the install script instead."

if [ -n "${FURY_REF:-}" ]; then
  info "updating agent-fury to $FURY_REF"
  pipx install --force "agent-fury[$EXTRAS] @ git+$REPO@$FURY_REF"
else
  # Re-pulls the latest from the recorded git spec, keeping your Python + extras.
  info "updating agent-fury to the latest"
  pipx reinstall agent-fury
fi

echo
echo "✅ updated — now on: $(fury --version 2>/dev/null || echo 'run: fury --version')"
