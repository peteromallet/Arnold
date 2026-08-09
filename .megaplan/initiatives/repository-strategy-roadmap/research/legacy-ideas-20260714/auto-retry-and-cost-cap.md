# Two related `megaplan auto` reliability/safety features

Bundled because both touch the auto-driver loop (`megaplan/auto.py`) and its
retry / termination logic. Ship them together so the flag surface is coherent.

## Task A — Auto-retry execute on codex context-window exhaustion

### Problem
When a long persistent codex session exhausts its context window, codex returns
this error text to the worker:

> Codex ran out of room in the model's context window. Start a new thread or
> clear earlier history before retrying.

Current behavior: auto-driver sees `phase 'execute' exited 1`, retries the same
`megaplan execute` subprocess (same session), fails the same way, and after
`--stall-threshold` iterations (default 5) bails with `stalled at state=finalized`.

We saw this IRL: sprint 2 execute completed 14/16 batches (~40 min of work) and
then burned 6 retry iterations + ~4 min of wall time before finally giving up —
requiring manual intervention (`megaplan execute --fresh --plan <name>`).

### Requirement
In `megaplan/auto.py`, when the execute phase exits non-zero AND the captured
subprocess stderr/stdout contains the fragment `"ran out of room in the model's context"`
(case-insensitive), the auto-driver must:

1. Log a clear message that context exhaustion was detected.
2. Re-run the execute phase with `--fresh` appended to the command.
3. Count this as a *separate retry category* — it should NOT count toward the
   normal stall threshold, and it should NOT happen more than `--max-context-retries`
   times per plan (default `2`).
4. If retries are exhausted AND the error keeps occurring, fall through to the
   existing stall logic (don't loop forever).

### CLI
- Add `--max-context-retries N` to `megaplan auto` (default `2`).
- No behavioral change when `N=0` (off).

### Tests
- Mock-subprocess test: execute "fails" with the context-exhaustion fragment in
  its output; auto-driver retries with `--fresh` appended; on second attempt the
  mock returns success; auto reaches terminal `done`.
- Mock-subprocess test: executed 3× with context-exhaustion error; with
  `--max-context-retries 2`, auto-driver stops retrying after the 2nd fresh retry.
- Regression: a generic execute failure (no context-exhaustion fragment) still
  goes through the existing stall-threshold path (not the fresh-retry path).

---

## Task B — Cost cap on `megaplan auto`

### Problem
`megaplan auto` can spend unbounded money. Receipts (Sprint 1) record
`cost_usd` per phase. The `state["history"]` also accumulates per-phase cost.
But nothing uses this for a pre-emptive abort — a runaway plan keeps spending.

### Requirement
Add `--max-cost-usd N` (float) to `megaplan auto`. After every phase subprocess
returns:

1. Sum `cost_usd` across every entry in `state["history"]`.
2. If the sum exceeds `N`, abort the auto loop with a new terminal outcome
   status `cost_cap_exceeded`.
3. Surface the final total and the cap in the outcome JSON so callers can see
   how far over they went on the last phase.
4. Default when unset: no cap (existing behavior).

The check runs *after* each phase completes — so a single phase that blows the
budget on its own still finishes (don't try to abort mid-phase), but the NEXT
phase won't launch.

### CLI
- `megaplan auto --max-cost-usd 5.00` — aborts after any phase pushes cumulative
  spend past $5.00.
- Invalid value (negative, non-numeric): argparse rejects with a clear message.

### Tests
- Mock-subprocess test: per-phase cost 1.00; `--max-cost-usd 2.50` → after phase 3
  the loop aborts with `cost_cap_exceeded` in the outcome.
- Mock-subprocess test: phase returns cost 10.00 (a single expensive phase);
  `--max-cost-usd 5.00` → that phase completes, *next* phase doesn't launch,
  outcome reports `cost_cap_exceeded`.
- Regression: when `--max-cost-usd` is unset, behavior is unchanged (no early
  termination regardless of cost).

---

## Combined success criteria

1. Both flags (`--max-context-retries`, `--max-cost-usd`) appear in
   `megaplan auto --help`.
2. All new tests pass alongside the existing test suite.
3. A manual smoke test with `--max-cost-usd 0.0001` aborts on the first phase
   that costs anything (proves the cap is evaluated after every phase).
4. A manual smoke test with a mock executor that emits the context-exhaustion
   error verifies the `--fresh` retry path actually runs.
5. The outcome JSON for both abort paths contains the new terminal status
   string (`cost_cap_exceeded` or `context_retry_exhausted`) and the full
   cost / retry counts.

## Out of scope

- Mid-phase cost limiting (cancelling a running subprocess).
- Retry strategies for non-context errors (e.g. rate limits, network).
- Cost prediction / forecasting before a phase runs.
- Cross-plan budgeting (per-plan only, not global).
