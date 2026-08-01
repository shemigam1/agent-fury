# agent-fury — Run & Test Guide

A hands-on runbook for installing, running, and testing agent-fury, plus the
observability stack and the eval harness. Every command here has been verified.

---

## 0. Prerequisites

- **Python 3.11–3.13** (use 3.13; 3.14 wheels for some deps are still spotty).
- **git** (for eval isolation via worktrees).
- Optional: **ripgrep** (`rg`) for fast `grep` (a Python fallback runs if absent).
- Optional: **Docker Desktop** (only for the observability stack).
- At least one LLM API key (Gemini, OpenAI, OpenRouter, or Anthropic), **or**
  a local Ollama for zero-key runs.

---

## 1. Install

```bash
# from the repo root
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"      # everything + test deps
```

Extras (mix and match instead of `all`): `openai` (OpenAI/OpenRouter/Ollama),
`anthropic`, `obs` (OpenTelemetry), `evals` (pyyaml), `dev` (pytest).

Install it as a **global CLI** instead:

```bash
pipx install .
```

Verify the binary:

```bash
fury --version
```

---

## 2. Configure API keys

Keys resolve in this order: **CLI flags → environment / `.env` → `~/.config/fury/config.toml`**.

Easiest: a `.env` in the repo (git-ignored, never committed):

```bash
echo 'GEMINI_API_KEY=your-key' > .env
```

Any of these are recognized: `GEMINI_API_KEY`, `OPENAI_API_KEY`,
`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`. Ollama needs no key.

Global config for an installed CLI — copy `config.example.toml` to
`~/.config/fury/config.toml` and fill in `[keys]` / `[defaults]`.

Check what's wired up:

```bash
fury models
```

```bash
fury config
```

---

## 3. Model specs

Pass `--model <provider:model>`. Aliases in parentheses.

| Spec | Notes |
| --- | --- |
| `gemini:flash` | → `gemini-flash-latest` (default) |
| `gemini:flash-lite` | smaller/cheaper Gemini |
| `openai:gpt-4o-mini` | needs `OPENAI_API_KEY` |
| `openrouter:deepseek/deepseek-chat` | hosted open-source; `OPENROUTER_API_KEY` |
| `ollama:qwen2.5-coder` | **local, no key** (needs Ollama running) |
| `anthropic:sonnet` | needs `ANTHROPIC_API_KEY` |

---

## 4. Run the agent

### Interactive REPL (default)

```bash
fury
```

`cd` into *any* repo first — fury operates on your current directory. Then chat
naturally, or use slash commands:

| command | does |
| --- | --- |
| `/model <spec>` | switch LLM **without losing context** |
| `/mode <code\|auto\|assistant>` | switch mode |
| `/models`, `/tools` | list providers / current tools |
| `/cost` | session tokens + estimated cost |
| `/clear`, `/cwd`, `/help`, `/exit` | utilities |

### One-shot (non-interactive / CI)

```bash
fury run "what does this service do?"
```

Note: mutating tools (write/edit/shell) prompt for approval in `code` mode. For a
hands-off one-shot that changes files, add `--yolo` or use `--mode auto`.

### The three modes

- **code** (default) — collaborative, asks before mutating actions.
- **auto** — autonomous: plans, then executes and self-checks without prompting.
- **assistant** — general-purpose, adds `web_search` / `web_fetch`.

```bash
fury --mode auto --yolo "add a --version flag and make the tests pass"
```

### Useful flags

`--dir <path>` (working dir), `--model`, `--mode`, `--yolo` (skip prompts),
`--plan-only` (read-only), `--verbose` (full tool output + cost), `--max-iters N`.

### Verify context survives a model switch

In the REPL:

```
> read fury/session.py and summarize switch_model
> /model openrouter:deepseek/deepseek-chat
> what did that function do again?   # answered from preserved context
```

---

## 5. Observability stack (optional)

Requires Docker running and the `obs` extra.

```bash
fury obs up
```

This starts OTel Collector + Tempo + Prometheus + Grafana. Then run the agent
with export enabled:

```bash
fury --telemetry run "list the python files and read one"
```

Open Grafana → **http://localhost:3000** → dashboards **agent-fury · Overview**
(tokens, cost, latency, tool errors) and **agent-fury · Evals**.

- Port 3000 taken? `FURY_GRAFANA_PORT=3001 fury obs up`, then use `:3001`.
- Other endpoints: Prometheus `:9090`, Tempo `:3200`.
- Tear down:

```bash
fury obs down
```

Quick metric check without Grafana:

```bash
curl -s 'http://localhost:9090/api/v1/query?query=fury_llm_requests_total'
```

---

## 6. Evals & leaderboard

Score how reliably models complete tasks against **any** repo. The target repo
is never mutated (each run uses an isolated git worktree / copy).

Task file (YAML or JSON) — each task is a prompt + a `verify` shell command whose
exit code is pass/fail:

```yaml
tasks:
  - id: create-marker
    prompt: "Create FURY_OK.txt at the repo root containing exactly BANANA."
    verify: "grep -qx BANANA FURY_OK.txt"
    timeout: 120
```

Run it (see `evals/tasks/example.yaml` for a ready-made suite):

```bash
fury evals --repo /path/to/repo --tasks evals/tasks/example.yaml --models gemini:flash-lite
```

Compare multiple models and push results to Grafana:

```bash
fury evals --repo /path/to/repo --tasks evals/tasks/example.yaml --models gemini:flash-lite,openrouter:deepseek/deepseek-chat --telemetry
```

Output: a terminal leaderboard + `fury-eval-report.md` and `.json` (override the
path with `--out`). Columns: success rate, avg iterations, tokens, cost,
duration, tool-error rate.

---

## 7. Run the test suite

```bash
pytest -q
```

Expect **34 passing**. Coverage:
- `test_tools.py` — sandbox containment, read/write/list.
- `test_history.py` — canonical conversation model.
- `test_providers.py` — Gemini/OpenAI/Anthropic serialization + a
  cross-provider **context-preservation** check.
- `test_phase2.py` — glob, grep, repomap, edit, `.gitignore` walking, pruning.
- `test_phase3.py` — telemetry (no-op + enabled), dashboards, packaged files.
- `test_phase4.py` — eval loading, scoring, worktree isolation, leaderboard.

Provider/obs/eval tests `importorskip` their extras, so install `.[all,dev]` to
run the full set. Handy subsets:

```bash
pytest -q tests/test_phase4.py
```

```bash
pytest -q -k "context or serial"
```

---

## 8. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `GEMINI_API_KEY is not set` | Put the key in `.env` (see §2); check `fury models`. |
| `429 RESOURCE_EXHAUSTED … limit: 5` | Per-minute free-tier cap; fury auto-backs-off. Wait or use another model. |
| `… PerDay … quotaValue: 20` | Daily free-tier cap hit (per model). Use another model or a billed key. |
| Grafana won't start, "port is already allocated" | `FURY_GRAFANA_PORT=3001 fury obs up`. |
| `Cannot connect to the Docker daemon` | Start Docker Desktop, then `fury obs up`. |
| `openai`/`anthropic`/`obs` import errors | Install the extra: `pip install -e ".[all]"`. |
| Slow/failed `pip install` on Python 3.14 | Use a 3.13 venv (see §0). |
| grep seems slow | Install `ripgrep` for the fast path (Python fallback works regardless). |

---

## 9. 60-second smoke test

```bash
source .venv/bin/activate && fury --version && fury models && pytest -q
```

Then, with a key set:

```bash
fury run --verbose "list the files here and tell me what this project is"
```
