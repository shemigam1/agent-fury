# 🔥 agent-fury

A multi-provider, **Claude-Code-style terminal coding agent** that works inside
*any* repository — JavaScript/TypeScript, Go, Rust, Python, or a mix. Install it
globally, `cd` into a project, and start delegating.

> Started life as a single-file Gemini script; now a provider-agnostic agent with
> a canonical conversation model, three operating modes, and an installable CLI.
> (Observability + an eval/benchmark harness are on the roadmap — see below.)

## Highlights

- **Switch LLMs mid-session without losing context.** One canonical conversation
  is translated to each provider's native format on the fly, so `/model` swaps the
  backend while every prior turn and tool result carries over.
- **Any provider:** Gemini (native), any **OpenAI-compatible** endpoint — OpenAI,
  **OpenRouter** (hosted open-source models), **Ollama / LM Studio / vLLM** (local)
  — and **native Anthropic (Claude)**.
- **Three modes:** `code` (collaborative), `auto` (autonomous planner → executor),
  `assistant` (general-purpose, with web search).
- **Language-agnostic:** no toolchain is hardcoded. The agent inspects the repo and
  runs its *own* tests/build (`npm test`, `go test ./...`, `cargo test`, `pytest`…).
- **Built for real codebases:** ripgrep-backed `grep`, `glob`, a ranked `repomap`,
  precise search/replace `edit_file`, chunked reads, `.gitignore` awareness, and
  automatic token-budget pruning so long tasks don't overflow the context window.
- **Safe by default:** every mutating/exec action asks permission (`--yolo` to skip,
  `--plan-only` for read-only), all file access is sandboxed to the working dir.

## Install

```bash
# isolated global tool (recommended)
pipx install .

# or into a venv for development
pip install -e ".[all,dev]"
```

Extras: `openai` (OpenAI/OpenRouter/Ollama), `anthropic`, `obs`, `evals`, or `all`.

## Configure

Keys are read from flags → environment / `.env` → `~/.config/fury/config.toml`.
Set whichever providers you use:

```ini
# .env or shell env
GEMINI_API_KEY=...
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
ANTHROPIC_API_KEY=...
# OLLAMA_BASE_URL defaults to http://localhost:11434/v1
```

Or a global config (see `config.example.toml`):

```toml
# ~/.config/fury/config.toml
[defaults]
model = "gemini:flash"
mode = "code"

[keys]
gemini = "..."
```

Check what's wired up:

```bash
fury models     # providers + which keys are set
fury config     # resolved configuration
```

## Use

```bash
fury                                  # interactive REPL in the current repo
fury --model anthropic:sonnet         # pick a model
fury --mode auto "add a /health endpoint and make the tests pass"
fury run "what does this service do?" # one-shot, non-interactive
```

### Model specs

```
gemini:flash                          openai:gpt-4o-mini
openrouter:deepseek/deepseek-chat     ollama:qwen2.5-coder
anthropic:sonnet
```

### Slash commands (in the REPL)

| command | does |
| --- | --- |
| `/model <spec>` | switch LLM, **keeping full context** |
| `/mode <code\|auto\|assistant>` | switch agent mode |
| `/models` · `/tools` | list providers / current tools |
| `/cost` | session token usage + estimated cost |
| `/clear` · `/cwd` · `/help` · `/exit` | utilities |

## Roadmap

- **Phase 1 ✅** — multi-provider core, 3 modes, REPL, packaging.
- **Phase 2 ✅** — real-codebase tooling: ripgrep `grep`, `glob`, `repomap`,
  search/replace `edit_file`, chunked reads, `.gitignore` + token-budget awareness.
- **Phase 3 ✅** — observability: OpenTelemetry (GenAI semantic conventions) →
  Collector → Tempo + Prometheus + Grafana (docker-compose, provisioned dashboards).
- **Phase 4 ✅** — evals: a repo-agnostic harness that scores task pass/fail by
  running a target repo's own verify command, producing a multi-model reliability
  leaderboard (metrics also flow to Grafana).

## Observability

Spin up a local Grafana stack and watch the agent's tokens, cost, latency, and
tool-error rate live (traces in Tempo, metrics in Prometheus):

```bash
pip install -e ".[obs]"     # OpenTelemetry SDK + OTLP exporter
fury obs up                 # starts collector + Tempo + Prometheus + Grafana (docker)
fury --telemetry            # run the agent with export enabled
# open Grafana → dashboard "agent-fury · Overview"
fury obs down               # tear the stack down
```

Instrumentation follows the OTel **GenAI semantic conventions** (`gen_ai.system`,
`gen_ai.request.model`, `gen_ai.usage.*`) plus `fury.*` extensions for cost and
tool errors, so the data is portable to any OTel backend. If port 3000 is taken,
set `FURY_GRAFANA_PORT`.

## Evals & reliability

Quantify how reliably a model completes real tasks, and compare models head-to-head.
A task file lists prompts, each with a `verify` shell command (exit code =
pass/fail), so it's language-agnostic. The target repo is never mutated — each run
happens in an isolated git worktree (or filtered copy).

```bash
pip install -e ".[evals]"
fury evals --repo /path/to/repo \
           --tasks evals/tasks/example.yaml \
           --models gemini:flash,openrouter:deepseek/deepseek-chat \
           --telemetry            # optional: push results to Grafana
```

Output is a per-model leaderboard (success rate, avg iterations, tokens, cost,
duration, tool-error rate) printed to the terminal and written to
`fury-eval-report.md` + `.json`. With `--telemetry`, the same metrics populate the
*agent-fury · Evals* Grafana dashboard.

## License

MIT
