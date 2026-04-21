# Megaplan

A planning and execution harness for structured phases — plan, critique, gate, revise, finalize, execute, and review — with independent critique and gating instead of one-shot attempts.

## Quick Start

Claude Code / Codex:

```
Please install megaplan and set it up for this project:

pip install megaplan-harness
megaplan setup

Once you're done, ask me what I need megaplan for.
```

OpenRouter / open models:

```
Please install megaplan with the open-model backend and set it up:

pip install megaplan-harness hermes-agent

Then create ~/.hermes/.env with:
OPENROUTER_API_KEY=<my key>

Then run: megaplan setup

Once you're done, ask me what I need megaplan for.
```

Get an OpenRouter key at [openrouter.ai/keys](https://openrouter.ai/keys). Any model on OpenRouter works.

## How it works

```
plan → critique → gate → [revise → critique → gate]* → finalize → execute → review
```

Each phase can use a different model. Independent critique and gating prevent rubber-stamping, and the visible `prep` phase makes repository investigation observable instead of hiding it inside `plan`.

Run the phases manually with:

```bash
megaplan init --project-dir . "Fix the authentication bug in login.py"
megaplan plan --plan <name>
megaplan critique --plan <name>
megaplan gate --plan <name>
megaplan finalize --plan <name>
megaplan execute --plan <name>
```

## Doc mode — planning documents instead of code

Pick the output mode at `init` with `--mode`: `--mode code` (default) produces a code diff; `--mode doc` produces a single document artifact at `--output <path>` (design spec, architecture doc, research note, RFC, proposal, post-mortem, migration plan — anything whose deliverable is prose, not code).

```bash
megaplan init --project-dir . --mode doc --output docs/new-cache-layer.md \
  "Design a two-tier cache for the ingest pipeline"
```

Doc mode respects every other flag (`--robustness`, `--auto-approve`, `--phase-model`, subagent mode, overrides) and uses authoring-focused prep/execute/review prompts plus a section-based execute schema (`sections_written`) instead of per-file changes.

A common pattern is to run `--mode doc` first, then `--mode code` against an idea that references that document.

### Looking for "metaplan" or "preplan" mode?

There is no `metaplan`, `preplan`, `meta-plan`, `pre-plan`, or `design-document mode`. For a design-first / preplan workflow, use `--mode doc`; `prep` is the visible repository-investigation *phase* inside every run, not a separate mode.

## Using different models per phase

Models with provider prefixes route to direct APIs. Models without a prefix go through OpenRouter:

```json
{
  "models": {
    "prep": "zhipu:glm-5.1",
    "plan": "zhipu:glm-5.1",
    "critique": "minimax:MiniMax-M2.7-highspeed",
    "execute": "zhipu:glm-5.1",
    "review": "minimax:MiniMax-M2.7-highspeed"
  }
}
```

Configure direct provider keys in `~/.hermes/.env`:

```bash
ZHIPU_API_KEY=...          # for zhipu: prefix
MINIMAX_API_KEY=...        # for minimax: prefix
GEMINI_API_KEY=...         # for google: prefix
```

## Robustness levels

- **light** — visible `prep` + one critique/revise pass, no gate or review
- **standard** — visible `prep` + 4 critique checks (default)
- **robust** — visible `prep` + 8 critique checks + parallel critique
- **superrobust** — same as robust + parallel review

## Observability

```bash
megaplan status --plan <name>
```

Use `status` to monitor `active_step`, `last_step`, notes, cost, execute progress, and next-step runtime guidance (`watch` remains a backward-compatible alias).

## Subagent mode (Claude Code / Codex)

Subagent mode delegates the full workflow to an autonomous agent and returns control only at defined breakpoints. It is the default orchestration mode for Claude Code and Codex; Cursor continues to run inline.

```bash
megaplan config set orchestration.mode subagent   # default
megaplan config set orchestration.mode inline      # switch back
```

## Configuration & Defaults

View all settings with `megaplan config show`. Override with `megaplan config set <key> <value>`. Reset with `megaplan config reset`.

| Key | Default | Description |
|-----|---------|-------------|
| `orchestration.mode` | `subagent` | `inline` or `subagent` (Claude Code and Codex) |
| `orchestration.max_critique_concurrency` | `2` | Max parallel critique checks |
| `execution.worker_timeout_seconds` | `7200` | Worker process timeout (seconds) |
| `execution.max_execute_no_progress` | `3` | No-progress execute attempts before escalation |
| `execution.max_review_rework_cycles` | `3` | Review→rework loops before force-proceeding |
| `agents.<step>` | varies | Agent for each phase (`claude`, `codex`, `hermes`) |

```bash
megaplan config set execution.worker_timeout_seconds 3600
megaplan config set agents.critique hermes
megaplan config reset
```

## SWE-bench Experiment

Megaplan is being tested live against Claude 4.5 Opus on SWE-bench Verified:

- **[Live dashboard](https://peteromallet.github.io/swe-bench-challenge/)** — watch the experiment in real time
- **[hermes-megaplan](https://github.com/peteromallet/hermes-megaplan)** — experiment orchestration code

## Code Health

<img src="scorecard.png" width="100%">

## License

MIT
