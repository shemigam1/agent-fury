#!/usr/bin/env bash
#
# agent-fury uninstaller.
#   curl -fsSL https://raw.githubusercontent.com/semil/agent-fury/main/uninstall.sh | bash
#
set -euo pipefail

info() { printf '\033[36m==>\033[0m %s\n' "$*"; }

if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q agent-fury; then
  info "removing agent-fury (pipx)"
  pipx uninstall agent-fury
else
  info "agent-fury not found via pipx"
  echo "   If you installed it in a venv, run: pip uninstall agent-fury"
fi

cat <<'EOF'

✅ agent-fury removed.

Your config and API keys at ~/.config/fury were left untouched.
Remove them too with:
  rm -rf ~/.config/fury

If you added a source line to your shell rc (~/.zshrc), delete the line:
  [ -f "$HOME/.config/fury/.env" ] && set -a && source "$HOME/.config/fury/.env" && set +a
EOF
