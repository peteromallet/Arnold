# Changelog

## v0.18.0 — 2026-04-15

### Automated tiebreaker triggering

Gate-driven automatic tiebreaker routing with budgeted, audited guardrails. Builds on the advisory `megaplan tiebreaker` subcommand from v0.17.0 — the harness now detects recurring constraint tensions and routes to tiebreaker automatically.

- **`TIEBREAKER` gate recommendation**: gate schema extended with `TIEBREAKER` as a fourth recommendation. Requires `tiebreaker_question`, `tiebreaker_flag_ids`, and `tiebreaker_fuzzy_group_id` fields.
- **Iteration-pressure analysis**: `megaplan/iteration_pressure.py` computes flag recurrence history — fuzzy-groups flags by Jaccard word similarity, tracks `addressed_then_reopened_count`, and renders a pressure table into the gate prompt context.
- **Mechanical recurrence validation**: harness validates TIEBREAKER recommendations against actual flag history. Re-prompts the gate once if no mechanical signal exists; force-demotes to ITERATE on second failure.
- **`tiebreaker_pending` / `tiebreaker_ready` states**: new plan states for the tiebreaker lifecycle. Both are automation-terminal — the auto/chain drivers stop cleanly.
- **`megaplan tiebreaker decide`**: CLI command to record human decisions (`--pick`, `--escalate`, `--replan`) with rationale. Writes to `tiebreaker_decisions.json` and transitions back to `critiqued`.
- **Settled-decision immunity**: critique prompt includes settled tiebreaker decisions. Critique is instructed not to re-raise settled concerns unless new evidence materially changes the premise.
- **Budget guardrails**: `max_tiebreakers_per_plan` (default 2), token budget (default 150k), time budget (default 30m). Exceeded budgets force-demote to ESCALATE.
- **Domain blocklist**: `tiebreaker_blocklist` config field skips tiebreaker for specified concern categories.
- **Spec-level opt-out**: `allow_tiebreaker: false` in idea front-matter or plan config disables the mechanism entirely.
- **Audit tracking**: `megaplan/audit.py` records tiebreaker usage, timing, and token costs. `megaplan tiebreaker audit` CLI for per-plan and global stats.

## v0.17.0 — 2026-04-15

### Verifiability contracts

Success criteria now declare which capabilities are needed to verify them, enabling pre-critique auditing and human-deferred verification.

- **Capability registry**: closed set of 11 mechanism-shaped strings in `megaplan/capabilities.py` — 6 container (`run_shell`, `read_files`, `run_tests`, `parse_diff`, `read_build_output`, `run_linter`) and 5 human (`drive_browser`, `inspect_runtime_ui`, `observe_runtime_logs`, `subjective_judgment`, `verify_physical_device`).
- **`requires` field on success criteria**: optional `requires: [cap1, cap2]` on each criterion in plan/revise schemas. Defaults to `[]` for backward compatibility.
- **Pre-critique audit**: `megaplan/verifiability.py` validates that `requires` entries are known capabilities and that the union of worker capabilities can satisfy them. Synthetic `verifiability` flags are injected into the critique phase.
- **`deferred_human` verdict**: review criteria that require human-only capabilities are marked `deferred_human` instead of `fail` or `waived`.
- **`awaiting_human_verify` state**: plans with deferred human criteria enter this automation-terminal state instead of `done`. The auto and chain drivers stop cleanly.
- **`megaplan verify-human`**: CLI command to record human verification evidence and transition from `awaiting_human_verify` to `done`.
- **`megaplan audit-verifiability`**: CLI command to inspect capability coverage of a plan's criteria without changing state.
- **`megaplan status --pending-human`**: lists plans in `awaiting_human_verify` state.
- **Auto/chain driver**: `drive()` returns `status="awaiting_human"` for plans in this state. Chain driver handles via its `on_failure` policy.
- **Migration**: `requires` defaults to `[]` via schema default. Existing plans work unchanged. `must` criteria with empty `requires` receive a deprecation advisory during critique.

### Tiebreaker subcommand (`megaplan tiebreaker`)

New advisory subcommand that produces structured decision context for architectural questions (e.g. when `gate` returns ESCALATE).

- **Two-agent pipeline**: a researcher agent gathers evidence and options, then a challenger agent stress-tests the findings — each in an independent ephemeral session.
- **CLI**: `megaplan tiebreaker --plan <name> --question "..."` (or `--question-file`), `megaplan tiebreaker status --plan <name>`.
- **Structured artifacts**: `tiebreaker_researcher.json`, `tiebreaker_challenger.json`, and a synthesized `tiebreaker.md` with decision-ready sections (options table, evidence summary, agreement/disagreement, fallback plan).
- **Idempotent**: re-runs produce versioned artifacts (`_v2`, `_v3`, …).
- **Advisory only**: does not modify plan state. Reuses existing worker dispatch (`run_step_with_worker`) and `SessionDB`.
- **Configurable agents**: `agents.tiebreaker_researcher` and `agents.tiebreaker_challenger` in config, defaulting to codex.

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
- **PyYAML** added as a runtime dependency.

### Tests

- `tests/test_chain.py` covers spec parsing, `chain status`, idea-file validation, seed-plan validation, happy-path execution (with `auto.drive` mocked), resume-from-`chain_state.json`, and on-failure `stop_chain`.

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
