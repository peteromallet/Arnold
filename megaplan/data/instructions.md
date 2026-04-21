# Megaplan
Route every step through the `megaplan` CLI. Never call agents directly.
Before the first CLI call, resolve a working launcher and reuse it for the whole run. Do not assume `megaplan` itself is on `PATH`; command presence alone is not enough. Prove the launcher works by successfully running a harmless CLI call with it first. In the instructions below, treat `<launcher>` as that verified command.
Launcher resolution order:
1. Try `python -m megaplan config show`.
2. If that fails, try `./.venv/bin/python -m megaplan config show`.
3. If that fails, try `uv run python -m megaplan config show`.
4. If that fails, try a version-selected shim such as `PYENV_VERSION=3.11.11 megaplan config show`.
5. Only use bare `megaplan ...` if that exact form already succeeded during this check.
## Triage
A single megaplan can cover as much as 2 weeks of work — don't reflexively split large efforts into multiple plans. Pick the right level based on the task:
- **Skip megaplan**: single-file fixes, bug fixes with clear cause, simple refactors, config changes, adding tests for existing code. Just do it.
- **Light**: multi-file changes with clear scope, well-understood features, straightforward additions. One critique pass, no gate, no review.
- **Standard** (default for megaplan): cross-cutting changes touching many subsystems, unfamiliar codebase areas, ambiguous requirements, changes with high breakage risk, or anything where the plan itself needs debate.
- **Heavy**: high-stakes changes where getting it wrong is expensive — security-critical code, data migrations, public API changes. Uses the same visible `prep` phase but with 8 critique checks instead of 4.

Default to standard unless the task is clearly simple enough for light. Do not ask the user to choose robustness — pick it yourself based on the above. Only ask execution mode (auto-approve or review) when using megaplan.
## Modes
Megaplan has two output modes, picked with `--mode` at `init`:
- **`--mode code`** (default): the run produces a code diff. Execute workers emit per-task file changes. Use for features, refactors, bug fixes, migrations — anything whose deliverable is source code.
- **`--mode metaplan`** (alias: `--mode doc`): the run produces a single document artifact at `--output <relative/path>` (e.g. `docs/design.md`). The prep, execute, and review phases use authoring-specific prompts; the execute schema uses `sections_written` instead of file changes; auditing reasons about section delivery. Use for design docs, architecture specs, research notes, RFCs, proposals, post-mortems, migration plans — anything whose deliverable is prose, not code. This is the "design-first / preplan" workflow; `prep` is the visible repository-investigation *phase* inside every run (both modes have it), not a separate mode.

`--from-doc <relative/path>` works with either mode. The path must be relative to `--project-dir`, must stay inside that directory, and must point to an existing file. When present, `init` imports any `## Settled Decisions` section from that prior doc artifact and stores the source path for later planning and execution context.

All other flags (`--robustness`, `--auto-approve`, `--phase-model`, `--hermes`, subagent mode, overrides, step editing) behave identically in both modes. The workflow phases are the same: `prep → plan → critique → gate → revise → finalize → execute → review`.

A common pattern is two runs: first `--mode metaplan` to produce a rigorous design document, then `--mode code --from-doc docs/design.md` on a new idea that references that document to implement it.

**`--mode` and `--output` go together.** `init` rejects `--output` without `--mode metaplan` (error `invalid_args`), and rejects `--mode metaplan` without `--output`. Don't try to pass one without the other.
## Start
Run `<launcher> config show` before `init`. If `raw_config.execution.auto_approve` is explicitly present, do not ask the execution-mode question and honor that configured override, including configured `false`. If that raw key is absent, ask execution mode (auto-approve or review) before `init`. In the same config check, respect `execution.robustness` as a settable override when it is configured; otherwise pick robustness yourself per the triage guidance above.
```bash
<launcher> init --project-dir "$PROJECT_DIR" [--auto-approve] [--robustness light|standard|robust|superrobust] [--mode code|metaplan] [--output docs/foo.md] [--from-doc docs/prior.md] "$IDEA"
```
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
At `--robustness light`, the loop is: `plan` → `critique` → `revise` → `finalize` → `execute`. There is no prep, no gate, and no review.
At `--robustness standard`, the loop is: `prep` → `plan` → `critique` → `gate` → ...
At `--robustness robust`, the loop is also `prep` → `plan` → `critique` → `gate` → ... but uses 8 critique checks instead of 4 and enables parallel critique.
At `--robustness superrobust`, the loop is the same as robust but also enables parallel review.
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
## Cloud Mode
`megaplan cloud` runs a plan inside a provider-managed container with a persistent workspace volume, so the run survives the user's terminal session. Suggest it for long-running plans that would outlast a local session or when the user wants an isolated persistent sandbox. Sprint 1 ships the `railway` provider only; `ssh` and `local` are planned.
Subcommands: `init`, `build`, `deploy`, `status`, `attach`, `logs`, `exec`, `resume`, `down`, `destroy`.
Typical flow: `megaplan cloud init` scaffolds `cloud.yaml`; edit it; export the secrets it lists; `megaplan cloud deploy`; then use `status`, `logs`, and `attach` to observe.
See `docs/cloud.md` for the full reference, including `cloud.yaml` fields, mode behavior (`auto`/`chain`/`idle`), secret handling, and troubleshooting.
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
```
