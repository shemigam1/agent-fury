# agent-fury

A multi-provider, **Claude-Code-style terminal coding agent** that works inside
*any* repository — JavaScript/TypeScript, Go, Rust, Python, or a mix. Install it
globally, `cd` into a project, and start delegating.

- **Switch LLMs mid-session without losing context.** One canonical conversation
  is translated to each provider's format on the fly, so `/model` swaps the
  backend while every prior turn and tool result carries over.
- **Any provider:** Gemini (native), any **OpenAI-compatible** endpoint — OpenAI,
  **OpenRouter** (hosted open-source), **Ollama / LM Studio / vLLM** (local) — and
  **native Anthropic (Claude)**.
- **Three modes:** `code` (collaborative), `auto` (autonomous planner → executor),
  `assistant` (general-purpose, with web search).
- **Built for real codebases:** ripgrep-backed `grep`, `glob`, a ranked `repomap`,
  precise search/replace `edit_file`, chunked reads, `.gitignore` awareness, and
  automatic token-budget pruning.
- **Observability & evals:** OpenTelemetry → Grafana dashboards, and a repo-agnostic
  eval harness that scores task pass/fail and ranks models on a reliability
  leaderboard.
- **Safe by default:** mutating/exec actions ask permission (`--yolo` to skip,
  `--plan-only` for read-only); all file access is sandboxed to the working dir.

---

## Install

One-liner (requires the repo to be public on GitHub):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/shemigam1/agent-fury/main/install.sh)"
```

It selects a compatible Python (3.11–3.13), ensures `pipx`, and installs the
`fury` command. Override the version/extras with `FURY_REF` / `FURY_EXTRAS`.

<details>
<summary>Manual install</summary>

```bash
# isolated global tool
pipx install ".[all]"

# or a dev environment
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
```

Extras: `openai` (OpenAI/OpenRouter/Ollama), `anthropic`, `obs`, `evals`, `all`.
</details>

### Update

Pull the latest without reinstalling (keeps your Python + extras):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/shemigam1/agent-fury/main/update.sh)"
```

### Uninstall

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/shemigam1/agent-fury/main/uninstall.sh)"
```

---

## Configure

Set at least one API key. fury reads keys from, in order: your shell environment,
a `.env` in the current repo, then a global `~/.config/fury/.env`. Simplest — the
global file (read automatically, works in any repo):

```bash
mkdir -p ~/.config/fury
printf 'GEMINI_API_KEY=your-key\n' > ~/.config/fury/.env
chmod 600 ~/.config/fury/.env
```

Recognized keys: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`,
`ANTHROPIC_API_KEY` (Ollama needs none). Check what's detected:

```bash
fury models
```

---

## Use

`cd` into any repo, then:

```bash
fury                                   # interactive REPL
fury --mode auto "add a /health endpoint and make the tests pass"
fury run "what does this service do?"  # one-shot, non-interactive
```

### Choosing a model

Pass `--model provider:model`, set `/model` in the REPL, or set a default in
`~/.config/fury/config.toml`:

```
gemini:flash-lite      openai:gpt-4o-mini      anthropic:sonnet
gemini:flash           openrouter:deepseek/deepseek-chat      ollama:qwen2.5-coder
```

### Slash commands (in the REPL)

| command | does |
| --- | --- |
| `/model <spec>` | switch LLM, **keeping full context** |
| `/mode <code\|auto\|assistant>` | switch agent mode |
| `/models` · `/tools` | list providers / current tools |
| `/cost` | session token usage + estimated cost |
| `/clear` · `/cwd` · `/help` | utilities |
| `/exit` · `exit` · `quit` | leave the REPL |

### Flags

`--dir <path>`, `--model`, `--mode`, `--yolo` (skip permission prompts),
`--plan-only` (read-only), `--verbose`, `--max-iters N`.

---

## Observability

Watch tokens, cost, latency, and tool-error rate live in Grafana (needs Docker
and the `obs` extra):

```bash
fury obs up          # OTel Collector + Tempo + Prometheus + Grafana
fury --telemetry     # run with export enabled → dashboards at http://localhost:3000
fury obs down
```

Set `FURY_GRAFANA_PORT` if port 3000 is taken.

---

## Evals

Score how reliably models complete tasks against any repo (never mutated — each
run uses an isolated git worktree). A task is a prompt + a `verify` shell command
(exit code = pass/fail), so it's language-agnostic.

```bash
fury evals --repo /path/to/repo \
           --tasks evals/tasks/example.yaml \
           --models gemini:flash-lite,openrouter:deepseek/deepseek-chat
```

Prints a per-model leaderboard and writes `fury-eval-report.md` / `.json`.

---

## Docs & tests

Full runbook: [`docs/GUIDE.md`](docs/GUIDE.md). Run the test suite with `pytest -q`.

## License

MIT
