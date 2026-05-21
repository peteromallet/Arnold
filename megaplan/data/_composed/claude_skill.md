---
name: megaplan
description: AI agent harness for coordinating Claude and GPT to make and execute extremely robust plans.
---

# Megaplan

**Scope:** This skill covers tooling — how to invoke and drive megaplan. For the decisions that come *before* invocation (scoping, brief, profile, robustness, depth), consult the **megaplan-decision** skill. If anything here contradicts megaplan-decision on decision-making content, megaplan-decision wins.

Route every step through the `megaplan` CLI. Never call agents directly.
Before the first CLI call, resolve a working launcher and reuse it for the whole run. Do not assume `megaplan` itself is on `PATH`; command presence alone is not enough. Prove the launcher works by successfully running a harmless CLI call with it first. In the instructions below, treat `<launcher>` as that verified command.
Launcher resolution order:
1. Try `python -m megaplan config show`.
2. If that fails, try `./.venv/bin/python -m megaplan config show`.
3. If that fails, try `uv run python -m megaplan config show`.
4. If that fails, try a version-selected shim such as `PYENV_VERSION=3.11.11 megaplan config show`.
5. Only use bare `megaplan ...` if that exact form already succeeded during this check.
## Triage
Decision-making (scoping, profile, robustness, depth, brief structure) lives in the **megaplan-decision** skill — consult it before running `megaplan init`. **Always run megaplan, even for tiny work** — `bare` robustness is the floor, never skip the harness. The few seconds of overhead pay back in the captured brief, plan, and outcome record.
## Modes
Megaplan has two output modes, picked with `--mode` at `init`:
- **`--mode code`** (default): the run produces a code diff. Execute workers emit per-task file changes. Use for features, refactors, bug fixes, migrations — anything whose deliverable is source code.
- **`--mode metaplan`** (alias: `--mode doc`): the run produces a single document artifact at `--output <relative/path>` (e.g. `docs/design.md`). The prep, execute, and review phases use authoring-specific prompts; the execute schema uses `sections_written` instead of file changes; auditing reasons about section delivery. Use for design docs, architecture specs, research notes, RFCs, proposals, post-mortems, migration plans — anything whose deliverable is prose, not code. This is the "design-first / preplan" workflow; `prep` is the visible repository-investigation *phase* inside every run (both modes have it), not a separate mode.

`--from-doc <relative/path>` works with either mode. The path must be relative to `--project-dir`, must stay inside that directory, and must point to an existing file. When present, `init` imports any `## Settled Decisions` section from that prior doc artifact and stores the source path for later planning and execution context.

All other flags (`--robustness`, `--auto-approve`, `--phase-model`, `--hermes`, subagent mode, overrides, step editing) behave identically in both modes. The workflow phases are the same: `prep → plan → critique → gate → revise → finalize → execute → review`.

A common pattern is two runs: first `--mode metaplan` to produce a rigorous design document, then `--mode code --from-doc docs/design.md` on a new idea that references that document to implement it.

**`--mode` and `--output` go together.** `init` rejects `--output` without `--mode metaplan` (error `invalid_args`), and rejects `--mode metaplan` without `--output`. Don't try to pass one without the other.
## Working tree default
Default to building on top of any existing uncommitted changes in the working tree, not stashing or resetting them. The plan author should treat the dirty tree as in-progress context the new work composes with. Only deviate when the existing changes directly contradict what the new plan needs to do — and then flag the conflict explicitly rather than silently overwriting.

## Start
Run `<launcher> config show` before `init`. If `raw_config.execution.auto_approve` is explicitly present, do not ask the execution-mode question and honor that configured override, including configured `false`. If that raw key is absent, ask execution mode (auto-approve or review) before `init`. In the same config check, respect `execution.robustness` as a settable override when it is configured; otherwise pick robustness yourself per the **megaplan-decision** skill.
```bash
<launcher> init --project-dir "$PROJECT_DIR" [--auto-approve] [--robustness bare|light|full|thorough|extreme] [--mode code|metaplan] [--output docs/foo.md] [--from-doc docs/prior.md] "$IDEA"
```
Legacy robustness names (`tiny|standard|robust|superrobust`) are still accepted on the CLI and in stored config — they map to `bare|full|thorough|extreme` respectively — but new plans should use the canonical names.
For metaplan-mode runs, pass `--mode metaplan --output <relative/path>` (the path is where the final document artifact is written, relative to the project dir). Everything else is identical to code mode.
Pass `--from-doc <relative/path>` when the new run should inherit decisions from a prior doc artifact. The path must be relative to the project dir, must exist as a file, and can be used with either `--mode code` or `--mode metaplan`. When the source doc contains a `## Settled Decisions` section, megaplan imports those decisions and automatically promotes them into success criteria for the new plan: `load_bearing: true` decisions become `must` criteria and `load_bearing: false` decisions become `info` criteria.
## Settled Decisions Section Format
When authoring a doc artifact that makes design decisions, use either of these canonical markdown shapes (the parser accepts both):

Bold-dash inline shape (preferred for short decisions):
```md
## Settled Decisions

- **SD-001** \u2014 Keep the current storage model. _load_bearing: true_
  Rationale: External integrations depend on it.
- **SD-002** \u2014 Default model is claude-sonnet-4-6. _load_bearing: false_
  Rationale: Balance of speed and capability.
```

YAML-ish shape (preferred when decisions need more fields):
```md
## Settled Decisions
- id: SD-001
  load_bearing: true
  decision: Keep the current storage model
  rationale: External integrations depend on it.
```
Use one list item per decision. Keep the `SD-NNN` convention (`SD-` prefix plus a number), store `load_bearing` as `true` or `false`, and indent continuation lines by two spaces beneath the list-item marker.
Report the plan name, execution mode, robustness, mode (and `--output` path when metaplan mode), current state, and next step.
## Workflow
Run the loop in this order:
1. `prep`
2. `plan`
3. `critique`
4. `gate`
5. `revise` when gate recommends iteration
6. `finalize`
7. `execute`
8. `review`
Use `next_step` and `valid_next` for CLI routing. After `gate`, follow `orchestrator_guidance` instead of manually interpreting gate signals. When a response includes `next_step_runtime`, use its `duration_hint` and `recommended_next_check_seconds` to calibrate timing.
At `--robustness bare`, the loop is: `plan` → `finalize` → `execute`. There is no prep, no critique, no gate, and no review.
At `--robustness light`, the loop is: `plan` → `critique` → `revise` → `finalize` → `execute`. There is no prep, no gate, and no review.
At `--robustness full`, the loop is: `prep` → `plan` → `critique` → `gate` → ...
At `--robustness thorough`, the loop is also `prep` → `plan` → `critique` → `gate` → ... but uses 8 critique checks instead of 4 and enables parallel critique.
At `--robustness extreme`, the loop is the same as thorough but also enables parallel review.
## Step Rules
- `plan`: inspect the repository first; produce the plan plus `questions`, `assumptions`, and `success_criteria`. Each criterion is `{"criterion": "...", "priority": "must|should|info"}`. `must` = hard gate (reviewer blocks), `should` = quality target (reviewer flags but doesn't block), `info` = human reference (reviewer skips).
- `prep`: make repository investigation explicit before planning. Respect `skip: true` when the task is already concrete enough.
- `critique`: surface concrete flags with concern, evidence, category, and severity; reuse open flag IDs; call out scope creep. Also validate that success criteria priorities are well-calibrated — `must` criteria should be verifiable yes/no, subjective goals should be `should`.
- `gate`: read the response, warnings, and `orchestrator_guidance`. (Skipped at light robustness.)
- `revise`: show the delta, flags addressed, and flags remaining. At light robustness, routes to `finalize`; otherwise loops back through `critique` and `gate`.
- `review`: judge success against the success criteria and the user's intent, not plan elegance. Only block on `must` criteria failures. `should` failures are flagged but don't require rework. `info` criteria are waived.
## Gate Principle
The gate response tells the orchestrator what to do next. Follow `orchestrator_guidance` unless you have a concrete reason to disagree after investigating the repository or plan artifacts yourself.
Investigate before disagreeing: read the current plan and critique artifacts, check the project code to verify whether a flagged issue is real, or use `megaplan status --plan <name>` / `megaplan audit --plan <name>`.
If you disagree with the guidance, explain why briefly and use an override. Do not manually reinterpret score trajectory, flag quality, or loop state when the gate already did that work for you.
## Execute
- After a successful gate, run `megaplan finalize` to produce the execution-ready briefing document.
- In auto-approve mode, run `megaplan execute --confirm-destructive` after finalize.
- In review mode, pause at the finalize-to-execute checkpoint and wait for explicit approval before running:
```bash
megaplan execute --confirm-destructive --user-approved
```
## Long-Running Execution
For plans with multiple batches, use per-batch mode to drive execution incrementally:
```bash
megaplan execute --plan <name> --confirm-destructive --user-approved --batch 1
megaplan execute --plan <name> --confirm-destructive --user-approved --batch 2
# ... continue until all batches complete
```
Between batches, poll progress:
```bash
megaplan progress --plan <name>
```
Use `megaplan status --plan <name>` for the full plan state, including active-step timing and any `next_step_runtime` guidance from the latest response.
Per-batch mode uses global batch numbering (1-indexed, computed from ALL tasks). Each `--batch N` call:
- Validates that batches 1..N-1 are complete
- Executes only batch N's tasks
- Writes `execution_batch_N.json` as evidence
- On the final batch, produces aggregate `execution.json` and transitions to `executed`
Timeout recovery: re-run the same `--batch N`. The harness checks prerequisite completion and merges only untracked tasks.
Note: `progress` shows completed state only (between-batch granularity). With per-batch mode, each batch is a separate CLI call, so the orchestrator has full visibility.
## Overrides
- `megaplan override add-note --plan <name> --note "..."`
- `megaplan override force-proceed --plan <name> --reason "..."`
- `megaplan override replan --plan <name> --reason "..." [--note "..."]`
- `megaplan override abort --plan <name> --reason "..."`
`force-proceed` is available from `critiqued` (routes to finalize, not execute). `replan` is available from `gated`, `finalized`, or `critiqued`. `add-note` is safe from any active state.
## Replan
Use `replan` when the orchestrator itself needs to edit the plan directly instead of asking the revise worker to do it.
```bash
megaplan override replan --plan <name> --reason "expanding scope" --note "Also clean up the display layer"
```
After `replan`, read the returned plan file, edit it directly, then run `megaplan critique`.
## Step Editing
Use `step` when you need to insert, remove, or reorder step sections (`## Step N:` or `### Step N:`) without hand-editing the markdown.
```bash
megaplan step add --plan <name> --after S3 "Add regression coverage for the parser"
megaplan step remove --plan <name> S4
megaplan step move --plan <name> S4 --after S2
```
Each edit writes a new same-iteration plan artifact, preserves the latest plan meta questions/success criteria/assumptions, and resets the plan to `planned` so it re-enters critique.
## Sessions And Autonomy
- Agents default to persistent sessions.
- `--fresh`: start a new persistent session.
- `--ephemeral`: one-off call with no saved session.
- `--persist`: explicit persistent mode.
- Keep moving and show results at each step.
- Only pause at finalize to execute in review mode.
## Configuration
View current defaults with `megaplan config show`. Override with `megaplan config set <key> <value>`. Reset with `megaplan config reset`.
When routing or behavior depends on config, check `megaplan config show` and respect user overrides instead of assuming defaults.
Settable execution keys: `execution.auto_approve`, `execution.robustness`.
## Profiles
A profile is a named preset that maps each workflow phase to an agent/model spec. Pass `--profile <name>` to any command that accepts `--phase-model` (`init`, `loop-init`, `tiebreaker`, etc.) to apply the preset.
See **megaplan-decision** for profile selection. Inspect available profiles with `megaplan config profiles list`.
Resolution order, later overrides earlier within the same name: built-in (`megaplan/profiles/*.toml`) → user (`~/.config/megaplan/profiles.toml`, or `$XDG_CONFIG_HOME/megaplan/profiles.toml`) → project (`<project_dir>/.megaplan/profiles.toml`).
Inspect with `megaplan config profiles list` and `megaplan config profiles show <name>`.
File format: TOML with a `[profiles.<name>]` table. Keys are phase names (`plan`, `prep`, `critique`, `revise`, `gate`, `finalize`, `execute`, `loop_plan`, `loop_execute`, `review`, `tiebreaker_researcher`, `tiebreaker_challenger`); values are agent specs like `"claude"`, `"codex"`, `"hermes:fireworks:accounts/fireworks/models/kimi-k2p6"`, `"hermes:glm-5.1"`. Example:
```toml
[profiles.my-mix]
plan     = "claude"
critique = "codex"
execute  = "hermes:fireworks:accounts/fireworks/models/kimi-k2p6"
review   = "codex"
```
`--phase-model` overrides on the CLI stack on top of any profile.
## Bakeoff
See the **bakeoff** skill for methodology and the **megaplan-decision** skill for when bake-offs earn their cost. This section covers the CLI mechanics once you've decided to run one.

`megaplan bakeoff run` runs the same idea through multiple profiles concurrently, each in its own git worktree, each driven autonomously by `megaplan auto`. Use it when the user wants to compare profiles head-to-head on the same task (e.g., "run this with kimi and the default profile side-by-side").
Supports `--mode code` (default) and `--mode doc` / `--mode metaplan` (alias). For doc-mode bake-offs, `--output <relative/path>` is required and is threaded into each profile's `megaplan init`; merge brings the chosen profile's doc artifact back to main instead of applying a code patch. Joke mode is not yet supported.
Requires a clean main worktree by default — pass `--allow-dirty` when there are unrelated uncommitted changes you want to keep on main. Those changes stay on main and are NOT copied into the worktrees, since worktrees branch off the current commit's SHA.
The idea must be a file (`--idea-file <path>`), not an inline string. Write the idea to a file first.
Bakeoff is inherently autonomous (it spawns `megaplan auto`), so the execution-mode question doesn't apply to bakeoff runs. `--robustness` is forwarded to each profile's `init`. When a project-layer `.megaplan/profiles.toml` exists, it's automatically copied into each worktree so project-only profiles resolve.
Lifecycle:
- `megaplan bakeoff run --idea-file <path> --profiles <p1> <p2> [--mode code|doc|metaplan] [--output <relative/path>] [--exp-id <id>] [--detach] [--robustness <level>] [--allow-dirty]` — kicks off N concurrent profile runs. Without `--detach` it streams a live status table every 5s and blocks until all profiles finish; with `--detach` it returns immediately and the user polls via `status`. `--output` is required with `--mode doc|metaplan` and rejected with `--mode code`.
- `megaplan bakeoff status [--exp <id>]` — current state of each profile (running / completed / crashed).
- `megaplan bakeoff tail [--exp <id>]` — tail the per-profile auto logs.
- `megaplan bakeoff compare --exp <id> [--judge <model>]` — collect metrics across profiles; with `--judge`, an LLM judge ranks the outputs.
- `megaplan bakeoff pick --exp <id> --profile <name> --rationale "..."` — record the human-selected winner.
- `megaplan bakeoff merge --exp <id>` — merge the chosen profile's worktree back to main.
- `megaplan bakeoff resume --exp <id>` — resume unfinished profile runs.
- `megaplan bakeoff abandon --exp <id>` — discard worktrees but keep audit data.
## Cloud Mode
`megaplan cloud` runs a plan inside a provider-managed container with a persistent workspace volume, so the run survives the user's terminal session. Suggest it for long-running plans that would outlast a local session, multi-repo work, or when the user wants an isolated persistent sandbox. Sprint 1 ships the `railway` provider only; `ssh` and `local` are planned.

Quick subcommand reference: `init`, `build`, `deploy`, `chain`, `status`, `attach`, `logs`, `exec`, `resume`, `down`, `destroy`. Typical flow: `megaplan cloud init` → edit `cloud.yaml` → export secrets → `megaplan cloud deploy` → `megaplan cloud chain <chain.yaml>`.

For the full reference — `cloud.yaml` fields, the `extra_repos[]` + `chain_session` multi-tenancy model, the operator loop, and the gotchas that wedge fresh runs (committed `chain_state.json`, profile-alias gap, secret-upload behavior, "internal_error" masking credit failures) — see the **megaplan-cloud** skill. Read it before launching the first cloud chain in a new project; the gotchas section will save hours.
## Tickets
`megaplan ticket new` creates a repo-scoped issue ticket. Use it when:
- During epic/plan work you notice an out-of-scope problem, bug, or rough edge
- A user explicitly asks you to capture something for later attention
- You want to log an observation that doesn't block the current task but should be tracked

The command prints only a ULID to stdout on success. Tickets live as `.megaplan/tickets/{ulid}-{slug}.md` files and are auto-discovered by the planner for future epics. Link them to epics with `megaplan ticket link <ticket> <epic> --resolves` so they auto-address when the epic completes.
## Feedback
See **megaplan-decision** for when to add the feedback phase (`--with-feedback`). This section covers the CLI mechanics once you've decided to use it.

`megaplan feedback --plan <name>` scaffolds a `feedback.md` file in the plan directory and opens it in `$EDITOR` (or `$VISUAL`). The file has one section per workflow stage — `prep`, `plan`, `critique`, `revise`, `gate`, `tiebreaker`, `finalize`, `execute`, `review` — plus an `Overall` section. Each section has a `rating:` (integer 0–10) and a free-form `comment:` field; leave any field blank to skip it.

This is **user feedback**, owned by the human after a run finishes — megaplan only scaffolds the template and parses it back on load, it never overwrites edits. Old plans without a `feedback.md` simply have no feedback attached; running `megaplan feedback --plan <name>` on an older plan scaffolds the template on demand (backwards compatible).

Use `megaplan feedback --plan <name> --show` to print the parsed summary, and `--no-edit` to just scaffold the template and print the path without launching an editor. Parsed feedback is exposed on the in-memory `Plan` record as `Plan.feedback` (a dict shaped `{"overall": {...}, "stages": {stage: {...}}}`), so downstream tooling can read it the same way as any other artifact. When `--actor`/`MEGAPLAN_ACTOR_ID` is set, parsed feedback is also written to the `plans.feedback` jsonb column so the DB and file backends stay in sync.

### Filling feedback with subagents
Recommended process when an agent (rather than the human) is producing the initial assessment:

1. **Scaffold**: run `megaplan feedback --plan <name> --no-edit` to create the empty `feedback.md`. Note the plan directory it prints — that is where the per-stage artifacts live (`plan_v*.md`, `critique*.json`, `gate.json`, `tiebreaker_*.json`, `finalize.json`, `execution*.json`, `review.json`, etc.).
2. **Per-stage assessment**: dispatch one read-only subagent per stage that actually ran (skip stages with no artifacts). Brief each subagent narrowly — give it the plan idea, the stage name, and the artifact filenames for that stage only. Ask it to return a 0–10 rating plus a 1–3 sentence comment grounded in what the artifacts show (what worked, what was weak, what was missed). Run these in parallel; they have no dependencies on each other.
3. **Synthesize Overall**: after the per-stage results come back, *you* (the orchestrating agent, not a subagent) read the per-stage ratings and comments together with the final outcome (`final.md`, `review.json`, any `latest_failure`) and decide an Overall rating and comment. The Overall is a judgment call about whether the run delivered the goal, not an average of stage ratings.
4. **Write**: edit `feedback.md` with the ratings and comments. Leave a stage blank if it didn't run or you can't form a defensible opinion — empty is better than guessed. Run `megaplan feedback --plan <name> --show` to confirm the parser picked everything up.

Keep comments grounded in specific artifact evidence ("critique flagged X but reviewer didn't catch the regression in Y") rather than vibes. The point of feedback is signal for future runs, not a participation score.

### Searching feedback across plans
`megaplan feedback search` queries every plan with non-empty feedback across both backends — local `feedback.md` files in this project tree plus, when an actor is configured, the `plans.feedback` jsonb column in the DB. Duplicates between backends are de-duped by (plan name, project_dir). Use this to answer "which profile actually scored well on this repo?" or "where did the executor get a 6 or below?". Filters:
- `--profile <substr>` — substring match on the plan's profile (e.g. `--profile claude` matches `all-claude`, `claude-led`, etc.).
- `--repo <substr>` — substring match on the plan's `project_dir` / repo path.
- `--min-rating N` / `--max-rating N` — bounds on the Overall rating.
- `--stage <name>` — only plans that recorded a rating for that stage (`plan`, `critique`, `execute`, …).
- `--has-comment` — only plans whose Overall comment is non-empty.
- `--all` — scan every megaplan project root on this machine, not just the current tree.
- `--json` — emit raw rows instead of a table.

Default output is a compact table (plan, profile, overall rating, backend, repo, plus the first line of the Overall comment). Combine with `megaplan feedback show --plan <name>` to drill into a specific match.
## Commands
```bash
megaplan status --plan <name>
megaplan progress --plan <name>
megaplan audit --plan <name>
megaplan list
megaplan prep --plan <name>
megaplan plan --plan <name>
megaplan critique --plan <name>
megaplan revise --plan <name>
megaplan gate --plan <name>
megaplan finalize --plan <name>
megaplan execute --plan <name> --confirm-destructive [--batch N]
megaplan review --plan <name>
megaplan step add --plan <name> [--after S<N>] "description"
megaplan step remove --plan <name> S<N>
megaplan step move --plan <name> S<N> --after S<M>
megaplan override add-note --plan <name> --note "..."
megaplan override force-proceed --plan <name> --reason "..."
megaplan override replan --plan <name> --reason "..." [--note "..."]
megaplan override abort --plan <name> --reason "..."
megaplan config show
megaplan config set <key> <value>
megaplan config reset
megaplan config profiles list
megaplan config profiles show <name>
megaplan bakeoff run --idea-file <path> --profiles <p1> <p2> [--mode code|doc|metaplan] [--output <relative/path>] [--exp-id <id>] [--detach] [--robustness <level>] [--allow-dirty]
megaplan bakeoff status [--exp <id>]
megaplan bakeoff tail [--exp <id>]
megaplan bakeoff compare --exp <id> [--judge <model>]
megaplan bakeoff pick --exp <id> --profile <name> --rationale "..."
megaplan bakeoff merge --exp <id>
megaplan bakeoff resume --exp <id>
megaplan bakeoff abandon --exp <id>
megaplan ticket new "title" -b "body"
megaplan ticket list [--status <s>] [--tags <t>] [--json]
megaplan ticket show <id> [--json]
megaplan ticket edit <id> [--title <t>] [--body <b>] [--status <s>]
megaplan ticket link <ticket> <epic> [--resolves]
megaplan ticket unlink <ticket> <epic>
megaplan ticket addressed <id> [--note <n>]
megaplan ticket dismiss <id> --reason "..."
megaplan ticket reopen <id>
megaplan feedback --plan <name> [--show] [--no-edit]
megaplan feedback search [--profile <s>] [--repo <s>] [--min-rating N] [--max-rating N] [--stage <name>] [--has-comment] [--all] [--json]
```


<!-- Source of truth for Claude-specific subagent orchestration. Appended only to the Claude skill via bundled_global_file('claude_skill.md'). -->
## Subagent Mode
This appendix is Claude-specific. It adds a subagent path; subagent mode is the default for Claude.

### Activation
- Default to subagent unless an inline override is explicitly set for this run or `megaplan config show` reports `"orchestration": {"mode": "inline"}`.
- Per-run override wins over config. If the run explicitly says `inline`, stay inline even when config prefers `subagent`.
- Use subagent mode for long multi-phase runs where keeping the outer conversation clean matters, especially auto-approve runs.
- Prefer inline mode for small edits, quick clarifications, or any run where the user wants to watch each phase in the main thread.

### Launch
When subagent mode is active, the outer skill becomes a launcher plus breakpoint relay. Start a Claude Code Agent with:
- `description`: `Run megaplan autonomously for {PROJECT_DIR}`
- `prompt`: fill the template below with `{IDEA}`, `{PROJECT_DIR}`, `{AUTO_APPROVE}`, `{AUTO_APPROVE_FLAG}`, `{ROBUSTNESS}`, and `{ROBUSTNESS_FLAG}`
- `run_in_background: true` when `{AUTO_APPROVE}` is true; otherwise foreground is fine
- Expand `{AUTO_APPROVE_FLAG}` to an empty string when `raw_config.execution.auto_approve` is explicitly set; otherwise expand it to `--auto-approve` for auto-approve runs and an empty string for review runs.
- Expand `{ROBUSTNESS_FLAG}` to an empty string when `raw_config.execution.robustness` is explicitly set; otherwise expand it to `--robustness {ROBUSTNESS}`.
- For doc-mode runs, also append `--mode doc --output <relative/path>` to the `megaplan init` call in the subagent's Startup step. Everything else in the template applies unchanged; the workflow phases and breakpoints are identical in doc mode.
- After editing this source file, rerun `megaplan setup --force` so installed `SKILL.md` files pick up the refreshed appendix.

### Outer Skill Handling
- Decide inline vs subagent before starting the workflow.
- In subagent mode, launch the agent, wait for either `BREAKPOINT:` or `COMPLETE:`, and keep the main thread thin.
- Support inject-after by letting the background subagent continue while the user runs `megaplan override add-note`; the next phase boundary picks it up from `megaplan status`.
- Support kill-and-inject by stopping the running subagent, appending a note with `megaplan override add-note`, and relaunching a new subagent on the same plan.
- When a breakpoint arrives, relay the summary to the user, collect the answer, and resume the same agent with `SendMessage` when possible.
- Parse only the explicit breakpoint header, not incidental text, when deciding whether the agent stopped intentionally.
- When completion arrives, report the final result back to the user without replaying every internal phase.

### Agent Prompt Template
```text
You are the autonomous megaplan runner for this single run.

Project: {PROJECT_DIR}
Idea: {IDEA}
Execution mode: {AUTO_APPROVE}
Robustness: {ROBUSTNESS}

## 1. Role & Mission
Your job is to drive the megaplan workflow through the CLI until the run finishes or a defined breakpoint requires the outer conversation.

Always follow these priorities, in order:
1. The latest user direction relayed through notes or resume messages.
2. The live CLI state from `megaplan status --plan <name>`.
3. The workflow and breakpoint rules in this template.
4. Your own memory of earlier turns.

Always do these things:
- Operate through the `megaplan` CLI only. Do not call workers or agents directly.
- Keep the outer conversation clean. Do not ask for routine confirmation.
- Use `next_step` and `valid_next` for routing. If memory and CLI state disagree, trust CLI state.
- Follow `orchestrator_guidance` after `gate` unless you have a concrete reason to disagree after checking plan artifacts or repository evidence yourself.
- Build on top of uncommitted changes in the working tree by default; only override if they directly contradict the plan.
- Treat user notes as authoritative.

Never do these things:
- Do not run the workflow manually outside the CLI.
- Do not skip required phases for the selected robustness level.
- Do not emit a breakpoint unless one of the breakpoint rules below says to.

## 2. Startup
Start the run like this:
1. Use empty-string expansion for `{AUTO_APPROVE_FLAG}` and `{ROBUSTNESS_FLAG}` whenever the corresponding `raw_config.execution` key is explicitly set.
2. Run `megaplan init --project-dir "{PROJECT_DIR}" {AUTO_APPROVE_FLAG} {ROBUSTNESS_FLAG} "{IDEA}"`.
3. Capture the returned plan name.
4. Output `PLAN_NAME: <name>` on its own line immediately after init and before any `BREAKPOINT:` or `COMPLETE:`.
5. Run `megaplan status --plan <name>`.
6. From then on, use that plan name for every command.

At startup and after every later resume:
- Read `state`, `next_step`, and `valid_next`.
- If `notes_count > 0`, read the full `notes` array before acting. Do not track note cursors or indexes; always read the full array.
- Treat all notes as context. If the newest note changes direction, treat that note as the new intent and decide whether to continue, revise, replan, or break out.
- If `active_step` is present, treat it as an in-flight phase marker rather than a completed step. Use `last_step` for the most recent completed phase.

## 3. Phase Routing by Robustness
Use the workflow below exactly. Canonical robustness names are `bare|light|full|thorough|extreme`; the legacy names `tiny|standard|robust|superrobust` map to `bare|full|thorough|extreme` and are still accepted.

Bare robustness:
- `init -> plan -> finalize -> execute -> done`
- There is no `prep`, no `critique`, no `gate`, no `review`.
- After `execute`, the CLI will end the run.

Light robustness:
- `init -> prep -> plan -> critique -> revise -> finalize -> execute -> done`
- There is no `gate`.
- There is no `review`.
- `prep` may return `skip: true`; that still counts as the visible prep phase.
- After the light `revise`, the CLI moves to `gated`, so the next command is `finalize`.
- After `execute`, the CLI will end the run.

Full robustness (legacy name: standard):
- `init -> prep -> plan -> critique -> gate`
- Then follow the gate decision tree below.
- `prep` may return `skip: true`; do not skip the command yourself.
- When you reach `gated`, run `finalize`.
- Then run `execute`.
- Then run `review`.
- If `review` returns `needs_rework`, the workflow becomes `finalized -> execute -> review` again until review passes or the CLI reaches its cap.

Thorough robustness (legacy name: robust):
- `init -> prep -> plan -> critique -> gate`
- `prep` may still return `skip: true`, but the phase remains visible in the CLI state/history.
- Uses 8 critique checks (vs 4 for full) and enables parallel critique.
- After that, thorough follows the same gate, finalize, execute, and review behavior as full.

Extreme robustness (legacy name: superrobust):
- Same as thorough, but also enables parallel review (review checks split across concurrent subagents).

Gate decision tree for full, thorough, and extreme:
- Condition 1: `gate_unset`
  Trigger: state is `critiqued` and `valid_next` includes `gate`.
  Action: run `megaplan gate --plan <name>`.
- Condition 2: `gate_iterate`
  Trigger: the latest gate recommendation is `ITERATE`, so `valid_next` includes `revise` but not `override force-proceed`.
  Action: run `megaplan revise --plan <name>`, then continue back through `critique` and `gate`.
- Condition 3: `gate_escalate`
  Trigger: the latest gate recommendation is `ESCALATE`, so `valid_next` offers `override add-note`, `override force-proceed`, or `override abort`.
  Action: stop with `BREAKPOINT: GATE_ESCALATE`.
- Condition 4: `gate_proceed_blocked`
  Trigger: the latest gate recommendation is `PROCEED`, but preflight still blocked execution, so state stays `critiqued` and `valid_next` offers `revise` plus `override force-proceed`.
  Action: do not finalize yet. Use `orchestrator_guidance` plus `preflight_results` to fix the blocking checks through `revise`. On iteration 1, the guidance text may stay generic, so inspect `preflight_results` yourself before revising. If the blocker cannot be resolved safely without a user decision, stop with `BREAKPOINT: GATE_BLOCKED`.
- Condition 5: `gate_proceed`
  Trigger: the latest gate recommendation is `PROCEED` and preflight passed, so state becomes `gated`.
  Action: run `megaplan finalize --plan <name>`.

Review routing for full, thorough, and extreme:
- If `review` succeeds, the run is done.
- If `review` returns `needs_rework`, the CLI moves back to `finalized` with `next_step` set to `execute`.
- When that happens, run `execute` again, then `review` again.
- This rework loop is capped by the CLI at 3 `needs_rework` cycles. If the cap is hit, the CLI force-proceeds to done and records the issue.

## 4. After Every Phase
After every phase command, immediately run:
`megaplan status --plan <name>`

Then do all of the following before choosing the next command:
- Re-read `state`, `next_step`, and `valid_next`.
- If `notes_count > 0`, read the full `notes` array; worker agents already receive all notes automatically.
- Check whether the newest note changes direction before the next CLI call.
- If the last phase was `gate`, treat `orchestrator_guidance` as a literal routing hint. Its lead text will be one of these exact forms:
  `First iteration; follow gate recommendation: <recommendation>.`
  `Plan passed gate and preflight. Proceed to finalize.`
  `Gate says PROCEED but preflight blocked. Fix: <checks>.`
  `Gate escalated. Ask the user: force-proceed, add-note, or abort.`
  `Score plateaued with recurring critiques the loop can't fix. Consider force-proceeding: \`megaplan override force-proceed --plan <name>\``
  `Score improving (<previous> -> <current>). Continue to revise.`
  `Score worsening (<previous> -> <current>). Investigate; the loop may be diverging.`
  `Gate recommends another iteration. Revise the plan.`
- On iteration 1, the first form takes precedence over the more specific `PROCEED` or `ESCALATE` strings, so use `recommendation`, `valid_next`, and `preflight_results` together.
- If `orchestrator_guidance` includes extra text after that lead string, treat it as appended hints about unresolved flags, recurring critiques, or scope creep.
- If the phase response and `status` disagree, trust `status`.
- If the next move is unclear, prefer the explicit `valid_next` list over your own reconstruction of the state machine.

## 5. Breakpoints
Use a breakpoint only for the cases in this section. Format every breakpoint exactly like this:

`BREAKPOINT: <type>`
`Plan: <name>`
`State: <state>`
`Summary: <short reason>`
`Context: <artifacts, warnings, or the exact user decision needed>`

Breakpoint types and triggers:
- `GATE_ESCALATE`
  Trigger: gate recommends `ESCALATE`, or `valid_next` offers `override add-note`, `override force-proceed`, or `override abort`.
- `GATE_BLOCKED`
  Trigger: you are in the `gate_proceed_blocked` branch and need the outer user to decide between more revision and `override force-proceed`.
- `EXECUTE_APPROVAL`
  Trigger: `finalize` succeeded in review mode and `execute` now requires explicit approval.
- `PHASE_ESCALATE`
  Trigger: a non-execute phase still fails after the required retry, or it returns unusable output twice.
- `EXECUTE_ESCALATE`
  Trigger: `execute` reaches the no-progress cap, or repeated blocking/timeouts prevent forward progress.

## 6. Safeguards
Non-execute safeguards:
- If any non-execute phase fails, returns unusable output, or clearly lands in a bad session state, retry that same phase once with `--fresh`.
- If the exact same error appears twice in a row for the same phase, the next retry must use `--fresh`.
- If the phase still fails after the required fresh retry, stop with `BREAKPOINT: PHASE_ESCALATE`.

Execute safeguards:
- Count whether each `execute` call creates forward progress.
- Forward progress means new completed tasks, a completed batch, or a state advance that clearly moves the run closer to done.
- If you hit 3 consecutive `execute` attempts without forward progress, stop with `BREAKPOINT: EXECUTE_ESCALATE`.
- If `execute` times out or is blocked, retry up to that same 3-attempt cap.

Review safeguards:
- `needs_rework` is a normal workflow branch, not a phase failure.
- If `review` returns `needs_rework`, do not break out. Follow the rework loop and run `execute` again from `finalized`.
- If `review` returns blocked instead of a real verdict, the CLI keeps the run in `executed` with `next_step` set to `review`.
- If `review` returns blocked or otherwise unusable output, treat that as a review-phase problem and apply the non-execute retry rule.

Notes and interruption safeguards:
- If the outer skill kills and relaunches you, start fresh with no reliable memory from the prior run.
- After any note injection or relaunch, run `megaplan status --plan <name>` immediately, read the full `notes` array, and treat all notes as context.
- Treat the most recent note as the relaunch explanation, then resume from `next_step`; the CLI state machine is the source of truth.

## 7. Resume Protocol
When the outer conversation resumes you with `SendMessage`, or when a new subagent is launched on an existing plan:
1. Re-read the message carefully.
2. Run `megaplan status --plan <name>`.
3. Read the full `notes` array.
4. Resume from the current CLI state and `next_step`, not from memory.

Resume rules:
- If the user grants execution approval, continue directly into `execute` with the correct approval flag.
- If the user answers a gate breakpoint, translate that answer into the minimum necessary action: continue revising, `override add-note`, `override force-proceed`, or `override abort`.
- If the user changes scope or intent materially, prefer `override replan`.
- After resuming, continue autonomously until the next defined breakpoint or completion.

## 7A. Note Injection from Outer Skill
- Use the stored `PLAN_NAME` for note and status calls. If it was not captured, run `megaplan list` and fall back to the most recent plan.
- Classify the user message: "add context for next phase" -> Option A, "change direction NOW" -> Option B, "just a question" -> answer without touching the run. Default to Option A unless the message clearly demands interruption.
- Option A (inject-at-boundary): run `megaplan override add-note --plan <name> --note "<note>"`, confirm to the user, and do not `TaskStop` or `SendMessage`.
- Option B (kill+relaunch): `TaskStop` the orchestrator, run `megaplan override add-note --plan <name> --note "<note>"`, relaunch a new orchestrator with prompt `Resume plan <name>. Run megaplan status to get current state, read all notes, and continue from where it left off.`, then confirm to the user.
- Latency: Option A can take up to one phase boundary; if that is not acceptable, the user should ask for Option B.

## 8. Execution Details
Finalize and execute:
- After `gated`, run `megaplan finalize --plan <name>`.
- In auto-approve mode, run `megaplan execute --plan <name> --confirm-destructive`.
- In review mode, stop with `BREAKPOINT: EXECUTE_APPROVAL`, then after approval run `megaplan execute --plan <name> --confirm-destructive --user-approved`.

Per-batch execution:
- If the execution briefing or CLI response indicates per-batch execution, continue batch by batch.
- Batch numbering is global and 1-indexed.
- Use `megaplan progress --plan <name>` between batch executions.
- Re-run the same batch number after a timeout if needed; the harness will reconcile previously completed work.

Execution loop end conditions:
- Continue until all actionable tasks are complete and the workflow reaches `done`.
- Stop early only for a defined breakpoint.

## 9. Overrides & Plan Editing
Override rules:
- `megaplan override add-note` is safe from any active state when you need to record new user direction without changing state.
- `megaplan override force-proceed` from `critiqued` moves the run into `gated`. Use it only when the user clearly wants to override the gate.
- `megaplan override force-proceed` cannot bypass a missing project directory or missing success criteria.
- `megaplan override force-proceed` from `executed` moves the run to `done`. Use that only when the user explicitly accepts unresolved review issues.
- `megaplan override abort` ends the run. Use it only when the user clearly wants to stop.
- `megaplan override replan` is available from `critiqued`, `gated`, or `finalized`. Use it when the orchestrator itself needs to edit the plan directly instead of asking the revise worker to do it.

Replan behavior:
- After `override replan`, read the latest plan file, edit it directly, then continue with `critique`.

Step editing:
- `megaplan step add`, `step remove`, and `step move` are available while the run is in `planned`, `critiqued`, `gated`, or `finalized`.
- Use them when you need to insert, remove, or reorder step sections without hand-editing the markdown.
- After a step edit, re-check `status` and continue from the returned state.

## 10. Completion Format
When the workflow completes, return exactly this shape:

`COMPLETE: megaplan run finished`
`Plan: <name>`
`Final state: <state>`
`Summary: <outcome>`
`Artifacts: <key files or reports>`
`Follow-up: <only if something remains>`

## 11. Command Reference
Core commands:
- `megaplan status --plan <name>`
- `megaplan progress --plan <name>`
- `megaplan audit --plan <name>`

Workflow commands:
- `megaplan prep --plan <name>`
- `megaplan plan --plan <name>`
- `megaplan critique --plan <name>`
- `megaplan gate --plan <name>`
- `megaplan revise --plan <name>`
- `megaplan finalize --plan <name>`
- `megaplan execute --plan <name> --confirm-destructive`
- `megaplan execute --plan <name> --confirm-destructive --user-approved`
- `megaplan execute --plan <name> --confirm-destructive --user-approved --batch N`
- `megaplan review --plan <name>`

Override and editing commands:
- `megaplan override add-note --plan <name> --note "..."`
- `megaplan override force-proceed --plan <name> --reason "..."`
- `megaplan override replan --plan <name> --reason "..." [--note "..."]`
- `megaplan override abort --plan <name> --reason "..."`
- `megaplan step add --plan <name> --after S<N> "description"`
- `megaplan step remove --plan <name> S<N>`
- `megaplan step move --plan <name> S<N> --after S<M>`
```
