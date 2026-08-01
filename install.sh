#!/usr/bin/env bash
#
# agent-fury installer.
#   curl -fsSL https://raw.githubusercontent.com/semil/agent-fury/main/install.sh | bash
#
# Overridable via env vars:
#   FURY_REF=v0.2.0   install a specific branch/tag (default: main)
#   FURY_EXTRAS=openai install a subset of extras   (default: all)
#   FURY_REPO=...      install from a fork
#
set -euo pipefail

REPO="${FURY_REPO:-https://github.com/semil/agent-fury.git}"
REF="${FURY_REF:-main}"
EXTRAS="${FURY_EXTRAS:-all}"

info() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Find a suitable Python (3.11–3.13; some deps lack 3.14 wheels).
find_python() {
  for py in python3.13 python3.12 python3.11; do
    command -v "$py" >/dev/null 2>&1 && { echo "$py"; return 0; }
  done
  if command -v python3 >/dev/null 2>&1; then
    case "$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')" in
      3.11|3.12|3.13) echo python3; return 0 ;;
    esac
  fi
  return 1
}

PY="$(find_python)" || die "need Python 3.11-3.13. Install one (e.g. 'brew install python@3.13') and re-run."
info "using $("$PY" --version 2>&1) ($PY)"

# 2. Ensure pipx (isolated global CLI installs).
if ! command -v pipx >/dev/null 2>&1; then
  info "installing pipx"
  if command -v brew >/dev/null 2>&1; then
    brew install pipx
  else
    "$PY" -m pip install --user pipx 2>/dev/null \
      || "$PY" -m pip install --user --break-system-packages pipx \
      || die "could not install pipx; install it manually then re-run."
  fi
  "$PY" -m pipx ensurepath >/dev/null 2>&1 || pipx ensurepath >/dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Install (or upgrade) agent-fury into its own environment.
info "installing agent-fury[$EXTRAS] from $REPO@$REF"
pipx install --python "$PY" --force "agent-fury[$EXTRAS] @ git+$REPO@$REF"

# 4. Next steps.
cat <<'EOF'

✅ agent-fury installed.  Verify:  fury --version

Add an API key (any provider you use):
  mkdir -p ~/.config/fury
  printf 'GEMINI_API_KEY=your-key\n' > ~/.config/fury/.env
  chmod 600 ~/.config/fury/.env

Load it in your shell (add to ~/.zshrc to make it automatic):
  set -a && source ~/.config/fury/.env && set +a

Then:
  fury models          # check which keys are detected
  cd any/repo && fury  # start the agent

If `fury` isn't found, open a new terminal (pipx just updated your PATH).
EOF
