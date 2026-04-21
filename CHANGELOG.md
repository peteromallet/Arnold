# Changelog

## v0.20.0 — 2026-04-21

### Sprint 2 cloud — chain commands, local + ssh providers, toolchain extensibility

Second sprint of the built-in cloud runner. Core megaplan gains chain ergonomics; cloud grows new providers and thin wrappers; the ad-hoc `~/Documents/reigh-megaplan-dev/` external folder is retired.

- **Core `megaplan chain start --spec <path>`**: validates the spec, resolves referenced idea files, kicks the auto-loop per milestone. Replaces the separate `init + auto` pair for chained milestones. Works locally without any cloud dependency.
- **Core `megaplan chain status --spec <path>`**: reads `chain_state.json`, prints `current_milestone`, `completed`, `remaining`, and per-milestone status. Human-readable block plus structured JSON `summary`.
- **Core `megaplan init --idea-file <path>`**: read the plan idea from a file instead of the positional CLI arg. Pairs with optional `--auto-start` to kick `auto` immediately after init.
- **Cloud wrappers (thin)**: `megaplan cloud chain <spec>` uploads the spec and invokes core `chain start` remotely; `megaplan cloud bootstrap <idea-file>` uploads an idea and invokes `init --idea-file --auto-start` remotely; `megaplan cloud status --chain` fetches the remote `chain_state.json` and runs the core formatter.
- **Local provider** (`provider: local`): docker-compose-backed runner for fast iteration and CI smoke tests. No Railway CLI, no cloud account. Template at `megaplan/cloud/templates/docker-compose.yaml.tmpl`.
- **SSH provider** (`provider: ssh`): plain docker-over-ssh. "Any host with docker + ssh" story. Supports persistent deploy dirs per-host.
- **Toolchain extensibility**: `toolchains:` block in `cloud.yaml` accepts named recipes (rust, go, java, or `custom` with a user-supplied install snippet). Template renderer appends matching Dockerfile stages so the baked image carries only what the target repo needs.
- **Secret redaction**: `megaplan cloud logs` output is passed through `megaplan/cloud/redact.py`, which masks values of declared `secrets:` keys as `***REDACTED***`. Follow-mode (`-f`) streams with the same redaction applied line-by-line.
- **`Provider.supports_session` capability**: session gating is now a capability flag on the provider ABC rather than a hardcoded `provider == "railway"` check in the CLI.
- **Reigh parity migration**: `docs/cloud-migration-from-reigh.md` documents the one-to-one field mapping between the old `~/Documents/reigh-megaplan-dev/` env vars and the new `cloud.yaml`. The external folder can be retired after running the parity deploy.

Concurrent refactors landing alongside sprint 2:
- `megaplan/handlers.py` (~6k lines) split into a `megaplan/handlers/` package by phase.
- `tests/test_megaplan.py` split into per-phase `test_critique.py`, `test_execute.py`, `test_finalize.py`, `test_gate.py`, `test_init_plan.py`, `test_prep.py`, `test_revise.py`.
- `--from-doc <path>` flag on `megaplan init` imports `## Settled Decisions` from a prior doc artifact into the new plan's success criteria.

## v0.19.0 — 2026-04-21

### Built-in cloud runner via `megaplan cloud`

Generalises the ad-hoc Railway container setup (previously external, at `~/Documents/reigh-megaplan-dev/`) into a built-in subcommand. Sprint 1 of two; scope is operational parity with the existing Railway flow.

- **New subcommand group**: `megaplan cloud {init,build,deploy,status,attach,logs,exec,resume,down,destroy}` covers the full lifecycle of a provider-backed run.
- **Subpackage layout** under `megaplan/cloud/`: `spec.py` (cloud.yaml loader + schema validation), `template.py` (renders `entrypoint.sh` / `railway.toml` / `cloud.yaml`), `cli.py` (argparse wiring, dispatched from `megaplan.cli`).
- **Provider plugin model**: `providers/` ships a `Provider` ABC plus a Railway plugin that wraps the `railway` CLI. Non-Railway providers (ssh, local) are explicit non-goals for this sprint.
- **Bundled templates**: `megaplan/cloud/templates/` ships `Dockerfile`, `entrypoint.sh.tmpl`, `healthserver.py`, `railway.toml.tmpl`, `cloud.yaml.tmpl`, and `chain.yaml.example`.
- **Extracted run wrappers**: `megaplan/cloud/wrappers/` ships `mp-run`, `mp-supervise`, `mp-heartbeat`, and `mp-chain` bash scripts, lifted out of the old entrypoint heredocs so they are versioned and editable.
- **`handle_init` strictness**: `--output` on a code-mode plan now raises `invalid_args` instead of being silently accepted. The only legitimate use of `--output` was a dropped `--mode doc` flag, which is now an explicit error.
- **Discoverability**: README gains a short "Cloud runs" section, `megaplan/data/instructions.md` gains a "Cloud Mode" block so the skill teaches Claude Code / Codex when to suggest `megaplan cloud`, and `.gitignore` now covers `.env` / `.env.*` / `*.env` since the cloud flow encourages `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GITHUB_TOKEN` secrets.
- **Out of scope for sprint 1**: ssh/local providers, `cloud init-plan` bootstrap, toolchain extensibility block, retiring the external reference folder. The existing `~/Documents/reigh-megaplan-dev/` keeps running unchanged.

### `--mode metaplan` alias for doc mode

- **CLI**: `megaplan init --mode metaplan` is now the preferred name for design/document runs. Internally it normalizes to `mode == "doc"`, so all existing state files, prompts, schemas, and downstream checks are untouched. `--mode doc` remains a valid alias.
- **Docs**: README section renamed to "Metaplan mode," with the defensive "Looking for metaplan/preplan?" subsection merged in now that metaplan is the real name. The SWE-bench Experiment section was dropped. Skill instructions updated to match.

### Doc-mode aggregator preserves executor output

- **Bug**: `assemble_doc` was overwriting the executor-authored output file with `executor_notes` (verification prose), so every doc-mode run ended with status-summary text instead of the intended deliverable. The executor is the authoritative author — the aggregator's only job is to fall back when the executor couldn't write to disk.
- **Fix**: `assemble_doc` now returns untouched if the output file exists with non-empty content. Empty or missing files still fall through to the degraded notes-based path; a docstring callout flags that its content is verification prose, not authored sections. Regression tests cover both branches.

### Misc

- Doc-mode / metaplan pointer landed pre-alias: README "Doc mode" section, `instructions.md` Modes block with a keyword-loaded "Looking for metaplan or preplan mode?" subsection, and `claude_subagent_appendix.md` note about the `--mode doc --output` flags the outer skill appends.
- README prose cleanup (light-megaplan run; no factual or code-example changes).
- License correction: README had claimed MIT; actual license per `LICENSE` and `pyproject.toml` is Open Source Native License (OSNL) 0.2.

## v0.18.1 — 2026-04-16

### Rework-cycle-aware stall detection in `megaplan auto`

Fixes a false-positive stall in the auto-driver when a plan is in a review→rework loop.

- **Bug**: `megaplan auto` counted iterations at the same `state` and bailed after `--stall-threshold` (default 5). When review returns `needs_rework`, state ping-pongs `finalized ↔ executed ↔ finalized` while execute re-runs batches. From the naive stall counter's view the plan looked "stuck at finalized for 5 iterations" even though new `review.json` / `execution.json` artifacts were being written and real progress was happening. Observed on plan `milestone-m1b-from-docs-state-20260416-1226` — 7 execute batches + 1 review cycle completed, driver exited rc=2.
- **Fix**: auto's driver loop now tracks `review.json` mtime as a forward-progress marker. When the marker advances, the stall counter resets and a rework-cycle counter increments. The new `--max-review-rework-cycles` flag (default 3, mirroring `execution.max_review_rework_cycles`) caps runaway rework loops independently of `--stall-threshold`.
- **Helpers**: `_resolve_plan_dir(plan, cwd)` walks up from cwd to find `.megaplan/plans/<plan>`, matching how `megaplan status` resolves plans. `_get_review_marker(plan_dir)` stats `review.json` and returns `None` for plans without a review artifact (e.g. light-robustness plans) — in that case the driver falls back to plain stall detection, preserving existing behavior.
- **CLI**: `--stall-threshold` help text updated to clarify that it fires only when state AND `review.json` are both unchanged. New `--max-review-rework-cycles` flag added with matching default.
- **Tests**: `tests/test_auto.py` (new file) covers stall reset on review-marker advance, rework cap enforcement, plain-stall fallback when no review.json exists, and the plan-dir resolver.
- **Scope**: auto.py driver loop only — execute and review phase logic are untouched.

## v0.18.0 — 2026-04-15

### Automated tiebreaker triggering

Gate-driven automatic tiebreaker routing with budgeted, audited guardrails. Builds on the advisory `megaplan tiebreaker` subcommand from v0.17.1 — the harness now detects recurring constraint tensions and routes to tiebreaker automatically.

- **Iteration-pressure analysis**: `megaplan/iteration_pressure.py` computes flag recurrence history — fuzzy-groups flags by Jaccard word similarity, tracks `addressed_then_reopened_count`, and renders a pressure table into the gate prompt context.
- **Mechanical recurrence validation**: harness validates TIEBREAKER recommendations against actual flag history via `_validate_tiebreaker`. Re-prompts the gate once if no mechanical signal exists; force-demotes to ITERATE on second failure.
- **`tiebreaker-run` top-level command**: auto-driver-callable command that invokes `_run_tiebreaker` inside a plan-locked context and transitions the plan state.
- **Gate integration**: `handle_gate` detects `TIEBREAKER` recommendations, runs the validator, transitions to `tiebreaker_pending` on approval.
- **Budget guardrails**: `max_tiebreakers_per_plan` (default 2). Exceeded budgets force-demote to ESCALATE.
- **Domain blocklist**: `tiebreaker_blocklist` config field skips tiebreaker for specified concern categories.
- **Spec-level opt-out**: `allow_tiebreaker: false` in config disables the mechanism entirely.
- **Audit tracking**: `megaplan/audit.py` records tiebreaker usage, timing, and token costs. `megaplan tiebreaker audit` CLI for per-plan and global stats. `handle_tiebreaker_decide` writes an audit record on every decision.
- **Auto driver**: `drive()` returns `status="awaiting_human"`, `"tiebreaker_pending"`, or `"tiebreaker_ready"` for the matching automation-terminal states and stops cleanly.
- **Gate prompt**: now includes the Iteration Pressure Analysis block; TIEBREAKER bullet explicitly cites `addressed_then_reopened_count` thresholds.

## v0.17.1 — 2026-04-15

### Tiebreaker subcommand (`megaplan tiebreaker`)

New advisory subcommand that produces structured decision context for architectural questions (e.g. when `gate` returns ESCALATE).

- **Two-agent pipeline**: a researcher agent gathers evidence and options, then a challenger agent stress-tests the findings — each in an independent ephemeral session.
- **CLI**: `megaplan tiebreaker --plan <name> --question "..."` (or `--question-file`), `megaplan tiebreaker status`, `megaplan tiebreaker decide --pick/--escalate/--replan --rationale`.
- **Structured artifacts**: `tiebreaker_researcher.json`, `tiebreaker_challenger.json`, and a synthesized `tiebreaker.md` with decision-ready sections (options table, evidence summary, agreement/disagreement, fallback plan).
- **Idempotent**: re-runs produce versioned artifacts (`_v2`, `_v3`, …).
- **Configurable agents**: `agents.tiebreaker_researcher` and `agents.tiebreaker_challenger` in config, defaulting to codex.
- **Gate schema**: `TIEBREAKER` added as fourth recommendation, with `tiebreaker_question`, `tiebreaker_flag_ids`, `tiebreaker_fuzzy_group_id` optional fields. Gate prompt documents the new option.
- **Plan lifecycle**: `tiebreaker_pending` / `tiebreaker_ready` states added with workflow transitions; both are automation-terminal.
- **Settled-decision immunity**: critique and revise prompts read `tiebreaker_decisions.json` and instruct agents not to re-raise settled concerns without materially new evidence.
- **Hot-fix**: `_run_tiebreaker` uses `WorkerResult.payload` instead of the nonexistent `.success`/`.parsed`/`.error` attributes — caught by live-cloud smoke run.

Automatic gate-driven tiebreaker routing (pressure analysis, budgeting, audit tracking) lands in v0.18.0.

## v0.17.0 — 2026-04-15

### Verifiability contracts

Success criteria now declare which capabilities are needed to verify them, enabling pre-critique auditing and human-deferred verification.

- **Capability registry**: closed set of 11 mechanism-shaped strings in `megaplan/capabilities.py` — 6 container (`run_shell`, `read_files`, `run_tests`, `parse_diff`, `read_build_output`, `run_linter`) and 5 human (`drive_browser`, `inspect_runtime_ui`, `observe_runtime_logs`, `subjective_judgment`, `verify_physical_device`).
- **`requires` field on success criteria**: optional `requires: [cap1, cap2]` on each criterion in plan/revise schemas. Defaults to `[]` for backward compatibility.
- **Pre-critique audit**: `megaplan/verifiability.py` validates that `requires` entries are known capabilities and that the union of worker capabilities can satisfy them. Synthetic `verifiability` flags are injected into the critique phase.
- **`deferred_human` verdict**: review criteria that require human-only capabilities are marked `deferred_human` instead of `fail` or `waived`.
- **`awaiting_human_verify` state**: plans with deferred human criteria enter this automation-terminal state instead of `done`.
- **`megaplan verify-human`**: CLI command to record human verification evidence and transition from `awaiting_human_verify` to `done`.
- **`megaplan audit-verifiability`**: CLI command to inspect capability coverage of a plan's criteria without changing state.
- **`megaplan status --pending-human`**: lists plans in `awaiting_human_verify` state.
- **Migration**: `requires` defaults to `[]` via schema default. Existing plans work unchanged.

## v0.16.0 — 2026-04-15

### Chain driver (`megaplan chain`)

New first-class subcommand that drives an ordered pipeline of milestone plans described by a YAML spec. Replaces ad-hoc bash orchestration (`chain.sh`) so plan-state logic lives in megaplan instead of fragile shell polling.

- **Spec-driven**: `megaplan chain --spec path/to/chain.yaml` reads milestones, optional seed plan, and failure/escalate policies from YAML.
- **Resumable**: progress is persisted to `chain_state.json` next to the spec (`current_milestone_index`, `current_plan_name`, `last_state`, `completed`). A relaunched process reads this file and picks up where the previous run stopped.
- **State-aware in the right layer**: each milestone is driven via the existing `megaplan.auto.drive` entry point, so phase selection (`plan → prep → critique → ... → review`) stays in megaplan. Shell wrappers no longer need to classify `next_step`.
- **`megaplan chain status --spec PATH`**: prints current chain progress without driving.
- **Failure/escalate policies**: `stop_chain` (default), `skip_milestone`, `retry_milestone`.
- **Seed handling**: if a seed plan is specified and not already in a terminal state, it is driven first under the same auto loop — fixing the gap where seed plans had no state-aware driver.
- **Validation**: up front, the chain driver checks every idea file exists and the seed plan (if set) resolves under the project root. Structured `invalid_spec` / `missing_idea_file` / `missing_seed_plan` errors.
- **`--no-git-refresh` flag**: suppresses the automatic `git checkout main && git pull` that runs before each milestone. Default: enabled (preserves existing CI/orchestrator behavior). Disable on developer checkouts where you do not want chain to stomp on the currently checked-out branch.
- **PyYAML** added as a runtime dependency.

### Tests

- `tests/test_chain.py` covers spec parsing, `chain status`, idea-file validation, seed-plan validation, happy-path execution (with `auto.drive` mocked), resume-from-`chain_state.json`, on-failure `stop_chain`, and `--no-git-refresh` suppression.

## v0.15.0 — 2026-04-15

### Doc mode

Megaplan can now run in `--mode doc`, letting execution produce a single document artifact instead of a code diff.

- `megaplan init` adds `--mode doc` and `--output <relative/path>` for document-targeted plans.
- Execute workers now support a doc-mode schema with `sections_written` instead of per-task file changes.
- Doc-mode prompt tracks reframe prep, execute, and review around authoring and document quality.
- Execution auditing can now reason about section-based delivery instead of only file-based changes.

## v0.14.6 — 2026-04-15

### Poisoned-session recovery

Fixes a class of infinite-loop failure where a persistent Codex/Claude session retained an obsolete "sandbox is broken" belief (e.g. an old `bwrap: Creating new namespace failed: Permission denied` line from before `MEGAPLAN_TRUSTED_CONTAINER=1` was wired up). On subsequent runs the model would read the stale history, refuse to execute, and return `status=blocked` — which megaplan then silently dropped as malformed, preventing any state progress and triggering supervisor restart loops.

- **Accept `status=blocked`**: `execution.py`, `execution_timeout.py`, and the execute/finalize JSON schemas now accept `blocked` as a valid task status. Blocked updates are merged and recorded instead of being silently discarded as malformed `task_updates`.
- **Detect poisoned sessions**: new `_is_poisoned_environmental_failure(raw)` helper matches known-stale sandbox error signatures. When it fires in `run_codex_step`/`run_claude_step` on a *resumed* session in *trusted-container* mode, megaplan drops the session id and recursively retries with `fresh=True`, mirroring the existing rollout-missing recovery from v0.14.3.
- **Surface blocked tasks**: the execute summary now lists blocked task IDs and emits a warning (`"N task(s) reported status=blocked by the worker — investigate executor_notes before continuing"`) so supervisors and humans see the real reason a batch did not advance instead of just `state=finalized`.
- **Status reports `tasks_blocked`**: CLI `status` output exposes `tasks_blocked` alongside `tasks_done` / `tasks_skipped` / `tasks_pending`.
- **Auto driver exits rc=5 on all-blocked stalls**: when `megaplan auto` detects a state-stall and every remaining task is `blocked` (no pending), it exits with status `blocked` / exit code 5 and a specific reason, distinct from generic `stalled=2` and `escalated=3`. Supervisors can treat this as a poisoned-worker signal and retry with `--fresh`.

## v0.14.5 — 2026-04-15

### Git-worktree isolation for subprocess workers

Fix: when megaplan invoked its `claude` / `codex` subprocess workers, it was passing the plan's stored `project_dir` as the `--add-dir` / `-C` target. Runs started from a git worktree would silently write source-code changes back into the main checkout, colliding with other concurrent runs.

- **CWD drives `--add-dir`**: `run_claude_step` now passes the CWD (or an explicit override) as `--add-dir` and subprocess cwd, instead of the plan's stored `project_dir`.
- **CWD drives Codex `-C`**: `run_codex_step` now passes the CWD as Codex's `-C` and as the `sandbox_workspace_write.writable_roots` entry. The `--add-dir` for Codex still points at the plan's artifacts directory (`plan_dir`), which is unchanged.
- **Plan state still lives at `project_dir`**: `.megaplan/plans/<name>/` artifacts remain co-located with the plan as before. Only the source-code working tree the worker sees has changed.
- **Divergence warning**: emits a one-time warning at startup when CWD differs from the plan's stored `project_dir`, so operators notice when a plan created in checkout A is being executed from worktree B.
- **`--work-dir PATH` flag**: every worker-invoking subcommand (`plan`, `prep`, `critique`, `revise`, `gate`, `finalize`, `execute`, `review`, `auto`, `loop-init`, `loop-run`) accepts `--work-dir` to explicitly override the detected CWD.

## v0.14.0 — 2026-04-15

### Strict gate flag resolution

The gate no longer silently accepts unresolved blocking flags on a PROCEED recommendation. PROCEED now requires explicit `flag_resolutions` for every blocking flag, and a retry is issued once when the first response still leaves blocking blockers unresolved.

- **No implicit acceptance**: unresolved blocking flags now trigger a single gate reprompt instead of being auto-marked as accepted tradeoffs.
- **Auto-downgrade on retry failure**: if the retry still leaves blocking flags unresolved, the gate artifact is rewritten as `ITERATE` with an auto-downgrade rationale note and `reprompted: true`.
- **Stricter tradeoff validation**: `accept_tradeoff` entries now require concrete, flag-specific rationale; rubber-stamp phrases are rejected the same way weak dispute evidence is rejected.
- **Debt derived from explicit resolutions**: accepted tradeoff debt entries now come from validated `flag_resolutions` rather than fallback unresolved-flag recording.
- **Gate test coverage refreshed**: existing gate debt tests now follow the strict-resolution contract, and new tests cover reprompt success, reprompt downgrade, rubber-stamp rejection, no-reprompt happy path, and resolution-derived debt recording.

## v0.12.0 — 2026-04-15

### Auto driver

New `megaplan auto --plan <name>` drives a plan from its current state to a terminal outcome without human intervention. The driver is intentionally dumb: it reads `status`, runs `next_step`, and loops. All real judgment stays in the phase logic.

- **Gate escalation policy**: ESCALATE defaults to force-proceed. Opt out with `--on-escalate abort` or `--on-escalate fail`.
- **Stall detection**: bails after N consecutive iterations in the same state (default 5).
- **Iteration cap**: hard stop at 200 iterations by default to bound runaway loops.
- **Structured exit codes**: `done=0`, `failed=1`, `stalled=2`, `escalated=3`, `cap=4` — so shell callers and CI can branch on terminal state without parsing output.
- Emits a JSON outcome with the final state snapshot and event log on exit.

### Cross-directory plan discovery

`resolve_plan_dir` now walks both parent and child directories to locate plans by name, so megaplan commands work from anywhere in a project tree — not just the directory containing `.megaplan/`.

- **`megaplan list --tree`**: list plans in the current subtree.
- **`megaplan list --all`**: system-wide plan discovery across the whole workspace.

### Standard robustness: init→plan transition

The `standard` robustness profile now picks up the init→plan transition that was previously only wired under heavier levels. Standard plans no longer stall after init waiting for a transition that never fires.

### Tests

Added `test_auto` coverage for the driver loop, escalation policies, stall detection, and iteration caps.

## v0.10.0 — 2026-04-10

### Codex backend hardening

The Codex (OpenAI) worker path got a major reliability overhaul, fixing a class of issues that caused silent failures, misclassified errors, and lost output when running with `--agent codex` or Hermes.

- **Timeout recovery**: when a Codex step times out, megaplan now attempts to recover partial output from the output file and stdout before raising. If valid structured output was produced before the timeout, the step succeeds instead of failing.
- **Per-step timeout caps**: non-execute steps (plan, critique, revise, etc.) are capped at 300s instead of inheriting the full 7200s worker timeout. Execute steps keep the full timeout.
- **Environment isolation**: child Codex processes no longer inherit `CODEX_THREAD_ID` or `CODEX_CI` from the parent, preventing workers from attaching to the wrong session.
- **Error classifier rewrite**: connection-level failures (DNS, WebSocket, stream disconnect) are now detected before HTTP status codes, fixing false positives where thread IDs or unrelated numbers were misclassified as 429s. Bare numeric patterns (`429`, `500`, etc.) now use word-boundary regex.
- **JSON extraction rewrite**: switched from greedy brace-matching to `JSONDecoder.raw_decode()`, which correctly handles trailing logs/traces after the JSON object.
- **Merged partial output**: timeout and crash error payloads now include both stderr/stdout and any file the worker managed to write, giving better diagnostics.

### Concurrency & observability

- **Plan locking**: all step handlers now acquire an `fcntl` file lock, preventing two processes from running steps on the same plan concurrently. Collisions produce a clear error naming the active step and agent.
- **Active step tracking**: `state.json` now carries an `active_step` field (`step`, `agent`, `mode`, `run_id`, `started_at`) set before the worker launches and cleared on completion or failure. Stale detection at 300s.
- **`megaplan status`**: now returns `active_step`, `last_step`, `total_cost_usd`, notes, and session summaries — everything the orchestrator needs without reading raw state.
- **`megaplan watch`**: new command combining `status` + `progress` into a single response for real-time monitoring.

### Tiny robustness level

New `--robustness tiny` mode stubs the critique and gate steps entirely, going straight from `plan` to `gated` to `finalize`. Useful for trivial tasks where the full critique loop is overhead.

### Parallel review for heavy mode

Heavy robustness now runs review checks in parallel (same pattern as parallel critique), splitting mechanical checks, sense checks, and task verification across concurrent workers.

### OpenAI strict-mode schema compatibility

- Recursive `required` reconciliation: all schema properties are now added to `required` arrays to satisfy OpenAI's structured output constraint that every property must be required.
- `flag_id` and `source` in review rework items changed from optional strings to required nullable (`["string", "null"]`).
- Gate `flag_resolutions` entries now require both `evidence` and `rationale` fields (use `""` for the one that doesn't apply).
- `accepted_tradeoffs` is now always returned (use `[]` when empty).

### Prompt improvements

- **Nested harness guard**: all worker prompts now include a preamble preventing the model from recursively invoking the `megaplan` CLI or skill.
- **Plan focus guidance**: planning prompt now tells the model to stop exploring once it has enough evidence, and to avoid `.megaplan/`, prior plan artifacts, and unrelated docs.
- **Standard robustness now includes prep**: removed the override that skipped the prep phase for standard robustness. All levels now run prep.

### Other

- License changed to OSNL 0.2.
- README updated: robustness level descriptions, observability section rewritten for `status`/`watch`.
- Comprehensive new test suites: `test_handle_review_robustness`, `test_parallel_review`, `test_review_checks`, `test_review_mechanical`, `test_tiny_robustness`, `test_config`, `test_io_git_patch`.
