# Changelog

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

## v0.14.5 — 2026-04-15

### Git-worktree isolation for subprocess workers

Fix: when megaplan invoked its `claude` / `codex` subprocess workers, it was passing the plan's stored `project_dir` as the `--add-dir` / `-C` target. Runs started from a git worktree would silently write source-code changes back into the main checkout, colliding with other concurrent runs.

- **CWD drives `--add-dir`**: `run_claude_step` now passes the CWD (or an explicit override) as `--add-dir` and subprocess cwd, instead of the plan's stored `project_dir`.
- **CWD drives Codex `-C`**: `run_codex_step` now passes the CWD as Codex's `-C` and as the `sandbox_workspace_write.writable_roots` entry. The `--add-dir` for Codex still points at the plan's artifacts directory (`plan_dir`), which is unchanged.
- **Plan state still lives at `project_dir`**: `.megaplan/plans/<name>/` artifacts remain co-located with the plan as before. Only the source-code working tree the worker sees has changed.
- **Divergence warning**: emits a one-time warning at startup when CWD differs from the plan's stored `project_dir`, so operators notice when a plan created in checkout A is being executed from worktree B.
- **`--work-dir PATH` flag**: every worker-invoking subcommand (`plan`, `prep`, `critique`, `revise`, `gate`, `finalize`, `execute`, `review`, `auto`, `loop-init`, `loop-run`) accepts `--work-dir` to explicitly override the detected CWD.

## v0.14.6 — 2026-04-15

### Poisoned-session recovery

Fixes a class of infinite-loop failure where a persistent Codex/Claude session retained an obsolete "sandbox is broken" belief (e.g. an old `bwrap: Creating new namespace failed: Permission denied` line from before `MEGAPLAN_TRUSTED_CONTAINER=1` was wired up). On subsequent runs the model would read the stale history, refuse to execute, and return `status=blocked` — which megaplan then silently dropped as malformed, preventing any state progress and triggering supervisor restart loops.

- **Accept `status=blocked`**: `execution.py`, `execution_timeout.py`, and the execute/finalize JSON schemas now accept `blocked` as a valid task status. Blocked updates are merged and recorded instead of being silently discarded as malformed `task_updates`.
- **Detect poisoned sessions**: new `_is_poisoned_environmental_failure(raw)` helper matches known-stale sandbox error signatures. When it fires in `run_codex_step`/`run_claude_step` on a *resumed* session in *trusted-container* mode, megaplan drops the session id and recursively retries with `fresh=True`, mirroring the existing rollout-missing recovery from v0.14.3.
- **Surface blocked tasks**: the execute summary now lists blocked task IDs and emits a warning (`"N task(s) reported status=blocked by the worker — investigate executor_notes before continuing"`) so supervisors and humans see the real reason a batch did not advance instead of just `state=finalized`.
- **Status reports `tasks_blocked`**: CLI `status` output exposes `tasks_blocked` alongside `tasks_done` / `tasks_skipped` / `tasks_pending`.
- **Auto driver exits rc=5 on all-blocked stalls**: when `megaplan auto` detects a state-stall and every remaining task is `blocked` (no pending), it exits with status `blocked` / exit code 5 and a specific reason, distinct from generic `stalled=2` and `escalated=3`. Supervisors can treat this as a poisoned-worker signal and retry with `--fresh`.

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
