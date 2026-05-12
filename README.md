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

pip install 'megaplan-harness[agent]'

Then create ~/.hermes/.env with:
OPENROUTER_API_KEY=<my key>

Then run: megaplan setup

Once you're done, ask me what I need megaplan for.
```

The `[agent]` extra installs the vendored Hermes backend dependencies.

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

## Metaplan mode — planning documents instead of code

Metaplan mode produces a single document artifact — design spec, architecture doc, research note, RFC, proposal, post-mortem, migration plan — instead of a code diff. Pick it at `init` with `--mode metaplan` (or `--mode doc`, the original flag name kept as an alias) and `--output <path>`:

```bash
megaplan init --project-dir . --mode metaplan --output docs/new-cache-layer.md \
  "Design a two-tier cache for the ingest pipeline"
```

It respects every other flag (`--robustness`, `--auto-approve`, `--phase-model`, subagent mode, overrides) and uses authoring-focused prep/execute/review prompts plus a section-based execute schema (`sections_written`) instead of per-file changes. A common pattern is to run metaplan mode first, then `--mode code` against an idea that references the resulting document.

Note: `prep` is a visible repository-investigation *phase* inside every run, not a separate mode.

## Using different models per phase

Every phase can run on a different model. Pick a named **profile** or override phases one at a time.

```bash
megaplan init --profile all-open "your idea"                    # all phases on open-source models
megaplan init --profile all-open --phase-model execute=claude "your idea"   # override one phase
```

Built-in profiles:

- **standard** — Claude for planning/revision, Codex for execution and critique (mirrors the default routing)
- **all-open** — Fireworks-hosted Kimi `kimi-k2p6` for planning/revision, `glm-5.1` for execution and critique (via Hermes)
- **all-deepseek-pro** — `deepseek-v4-pro` for every phase (via Fireworks)
- **all-deepseek-flash** — native DeepSeek `deepseek-v4-flash` for every phase (via Hermes)
- **all-fireworks-deepseek** — Fireworks-hosted DeepSeek for every phase (via Hermes)

Define your own in `.megaplan/profiles.toml` (per-project) or `~/.config/megaplan/profiles.toml` (user-wide):

```toml
[profiles.my-mix]
plan     = "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"
execute  = "hermes:glm-5.1"
review   = "codex"
```

Inspect with `megaplan config profiles list` and `megaplan config profiles show <name>`.

Model strings take the form `<agent>[:<model>]`. Agents are `claude`, `codex`, or `hermes`. After `hermes:`, a slug with a slash (e.g. `meta-llama/llama-3.3-70b`) routes via OpenRouter; a prefixed direct model (`deepseek:deepseek-v4-pro`, `hermes:fireworks:accounts/fireworks/models/kimi-k2p6`) uses that provider directly; a bare name (`glm-5.1`) uses the matching direct provider. Direct-provider keys live in `~/.hermes/.env`:

```bash
OPENROUTER_API_KEY=...
ZHIPU_API_KEY=...          # for glm-* direct
MINIMAX_API_KEY=...        # for MiniMax-* direct
DEEPSEEK_API_KEY=...       # for deepseek:* direct
FIREWORKS_API_KEY=...      # for fireworks:* direct
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

## Cloud runs

`megaplan cloud` deploys a plan to a remote runner backed by a persistent workspace volume. Sprint 2 adds `local` and `ssh` providers plus thin wrapper workflows for `megaplan cloud bootstrap <idea-file>`, `megaplan cloud chain <spec>`, and `megaplan cloud status --chain`. See [docs/cloud.md](docs/cloud.md) for `cloud.yaml` fields, provider notes, file-staging workflows, marker behavior, and log-redaction scope.

```bash
megaplan cloud init       # scaffold cloud.yaml
megaplan cloud deploy     # upload secrets and launch the runner
megaplan cloud bootstrap ideas/tiny.txt
```

## Bake-off runs

`megaplan bakeoff` runs the same idea through multiple profiles concurrently, one detached git worktree per profile, then archives all evaluation data while merging only the human-selected winner's code changes.

```bash
megaplan bakeoff run --idea-file ideas/cache.md --profiles standard all-open all-kimi --exp-id cache-bakeoff
megaplan bakeoff status --exp cache-bakeoff
megaplan bakeoff tail --exp cache-bakeoff --profile standard
megaplan bakeoff compare --exp cache-bakeoff
megaplan bakeoff pick --exp cache-bakeoff --profile standard --rationale "Best review result and smallest diff."
megaplan bakeoff merge --exp cache-bakeoff
```

The comparison step is explicit and re-runnable. It writes `.megaplan/bakeoffs/<exp-id>/comparison.json` and `comparison.md`; `pick` records the final human decision; `merge` applies the winner patch to the main tree and copies every profile's audit archive. Use `resume` to relaunch only non-terminal profiles, and `abandon` to remove retained worktrees while keeping the bake-off archive:

```bash
megaplan bakeoff resume --exp cache-bakeoff
megaplan bakeoff abandon --exp cache-bakeoff
```

Judge contract:

- Omit `--judge` -> skip (no paid call).
- `--judge auto` -> first free of `claude`/`codex`/`gpt-5` with canonical agent+model comparison.
- `--judge <model>` -> explicit.

## Subagent mode (Claude Code / Codex)

Subagent mode delegates the full workflow to an autonomous agent and returns control only at defined breakpoints. It is the default orchestration mode for Claude Code and Codex; Cursor continues to run inline.

```bash
megaplan config set orchestration.mode subagent   # default
megaplan config set orchestration.mode inline      # switch back
```

## Database mode

By default megaplan keeps state in `.megaplan/` on local disk. Switch to a Supabase Postgres database when you want shared state across machines, cloud runs, or multi-agent setups. Paste this to your agent:

```
Please set megaplan up in database mode.

0. Install the DB extra (psycopg lives behind it):

     pip install 'megaplan-harness[db]'

1. Connection string. If SUPABASE_DB_URL isn't already exported, ask me which
   Supabase project to use, then walk me through fetching it:
     Supabase dashboard → Project Settings → Database → Connection string.
   Use the **Direct connection** URI (port 5432) — NOT the transaction-mode
   pooler (port 6543), which drops the session config var that `set_actor`
   relies on. The password is the one I picked when I created the project;
   I can reset it from the same page if I've forgotten it. Export it as
   SUPABASE_DB_URL.

2. Schema. Apply every file in supabase/migrations/*.sql, in filename order,
   against SUPABASE_DB_URL. Use `supabase db push` if I have the Supabase CLI
   linked; otherwise loop `psql "$SUPABASE_DB_URL" -f <file>`.

3. Register me as an actor. Pick a short slug for me (e.g. my GitHub handle),
   then run:

     python -c "import uuid; from megaplan.store.db import DBStore; \
     DBStore().create_automation_actor(actor_id='<slug>', name='<my name>', \
     granted_epic_ids='*', actor_kind='human', idempotency_key=str(uuid.uuid4()))"

   Add `export MEGAPLAN_ACTOR_ID=<slug>` to my shell profile. That env var
   alone is enough to switch megaplan into DB mode — no per-command flag.

4. Optional — blob uploads. To stash large artifacts in Supabase Storage
   instead of `.megaplan/db-blobs/`, first create a bucket under the
   dashboard's Storage tab (private is fine), then export:
     - SUPABASE_URL              → Project Settings → API → Project URL
     - SUPABASE_SERVICE_ROLE_KEY → Project Settings → API → `service_role` key
       (sensitive; server-side only — never commit or expose to a browser)
     - SUPABASE_STORAGE_BUCKET   → the bucket name from the step above

Confirm by running `megaplan init "test idea"` and checking that a row lands
in the `epics` table.
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

## Code Health

<img src="scorecard.png" width="100%">

## License

[Open Source Native License (OSNL) 0.2](LICENSE). Free for internal use by anyone, including commercial companies. Redistribution inside a product or service is free for entities that open-source their own primary assets; otherwise requires a separate commercial license. See [LICENSE](LICENSE) for the full terms.
