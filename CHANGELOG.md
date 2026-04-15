# Changelog

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
