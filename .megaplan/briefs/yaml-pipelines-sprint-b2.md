# Sprint B2 — Planning pipeline runtime-selection cutover

> **Superseded by [sprint-b-revised.md](sprint-b-revised.md).** The YAML
> runtime is dead. Runtime-selection (`pipeline_runtime: legacy | yaml`)
> is obsolete — `compile_planning_pipeline()` in Python IS the canonical
> planning pipeline. Do NOT execute this brief.

## Goal

Make `megaplan plan` capable of running on the YAML runtime (Sprint A built, Sprint B1 extended) as a **runtime-selection** migration — not a behavioral re-implementation. Both `planning.py` and the new YAML path invoke the same handler internals (the seven named handlers from Sprint A's audit). What changes is the routing/dispatch/edge layer.

Three Codex reviews trimmed the original Sprint B brief dramatically. The trims preserve the actual goal (planning runs on YAML, default flippable) while dropping ceremony (14-day drain), gold-plating (5-input real-model corpus + ±15% cost math), and risky over-reach (deleting `planning.py` in the same sprint). **Phase 0 criteria rewrite is RETAINED** — your decision #5 was "no human sign-off"; cutting it would abandon that goal.

## Prerequisites (must be merged to main before kicking off)

1. **Sprint A** ✓ (commit `b3de5be2` + merge `fb6aea3c`) — YAML runtime + writing-panel-strict + handler audit appendix.
2. **Cache-fix** ✓ (commit `2d8d5bdc`) — three-layer defense against session cache-replay.
3. **Sprint B1** — executor + schema prerequisites including `HandlerStepSpec`, `merge: structural`, typed `kind="override"` edge compilation, `_run_parallel_stage` helper, `accept-cache-hit` override verb, `runtime-audit` command. **Without B1, B2 cannot land.** Verify with `git log --oneline main | head -10` for the B1 merge.

## What B2 actually delivers

A **runtime-selection migration**:

- `megaplan/pipelines/planning/pipeline.yaml` becomes a real YAML pipeline (replacing Sprint A's parked stub). Its stages are handler-backed using the seven named entries from B1's allowlist — same `_step_for`-style dispatch as `planning.py` today, just expressed in YAML.
- `pipeline_runtime: "legacy" | "yaml"` field in `state.json`. Set at `init` based on which path was chosen. Read at `resume` to dispatch correctly. **Missing field means `legacy`** (load-bearing default).
- `--use-yaml-pipeline` / `--use-legacy-pipeline` flags on `megaplan init` (and `megaplan plan` alias). Reject contradictory state on resume (legacy plan + `--use-yaml-pipeline` flag → fail loud, do not silently re-interpret).
- **Trace-parity test** verifying that the YAML path invokes the same handlers in the same order, makes the same edge dispatches, and produces the same state transitions as `planning.py` on a representative input. NOT a 5-input real-model corpus; NOT cost/token math.
- **One real-model smoke run** on a representative brief to confirm end-to-end behavior.
- **Phase 0 criteria rewrite** — eliminate `subjective_judgment` from criteria 0, 36, 37, 38, 39, 40.
- **`runtime-audit` enforcement** for the default-flip and deletion gates (replacing the 14-day drain).

## What B2 does NOT do (trimmed)

- **Does NOT delete `planning.py`.** Leave both paths alive indefinitely. Deletion is a separate sprint after weeks of YAML uptime. File a tracking ticket; don't force the timeline.
- **Does NOT build a 5-6 input real-model parity corpus** or compute ±15% cost stats. With seven handler escape-hatches, both paths invoke the same internals — trace parity covers what's actually different. One smoke run confirms end-to-end.
- **Does NOT enforce a 14-day calendar drain** before any deletion. `runtime-audit --fail-on-unsafe-cutover` (from B1) gates deletion based on actual plan state, not wall-clock time.

## Locked decisions

### 1. The seven named handlers (from B1's allowlist)

The pipeline.yaml uses HandlerStepSpec entries for exactly these seven phase wrappers — same as `planning.py`'s `_step_for` table:

1. `handle_critique`
2. `_validate_tiebreaker`
3. `handle_gate`
4. `handle_execute`
5. `handle_review`
6. `handle_tiebreaker_decide`
7. `handle_override`

An 8th name is an escalation trigger, not a quiet addition. Each handler entry pairs with a tracked ticket explaining why it's a handler (already exists from Sprint A's audit; verify each reference).

### 2. Phase 0 criteria — REWRITTEN, not deferred

The original Sprint B attempt escalated partly because of recurring critique failures on Phase 0's six `subjective_judgment` criteria (0, 36, 37, 38, 39, 40). Decision #5 was "no human sign-off, make decisions in advance."

**Locked path** (single, no OR):

For each of the six criteria:
- **If the criterion can be reworded as an objective test** using existing artifact fields (`review.json::recommendation`, `gate.json::settled_decisions`, `state.json::iteration`, etc.), reword it. Example: "criterion 36: human verifies implementation correctness" → "criterion 36: `review.json::recommendation == 'proceed'` AND `len([c for c in review.checks if c.verdict == 'fail']) == 0`".
- **If the criterion is genuinely subjective and cannot be reworded**, the brief PRE-DECIDES the answer as a locked decision in `pipelines/planning/pipeline.yaml` itself (e.g. via a `settled_decisions:` block at pipeline level). Criterion becomes "decision X was made in advance and is recorded at <location>".

**Implementation reality** (per Lens 1's finding): the current `audit-verifiability` checks `requires` capability strings, not shell-command output. The rewrite uses existing artifact-field assertions, NOT new shell-command verifiers. No new verifier infrastructure needed for B2 — just better criterion wording.

If a criterion genuinely cannot be reworded AND cannot be pre-decided, that's an escalation — surface as an open question, don't silently leave it as `subjective_judgment`.

Verifiable: `megaplan audit-verifiability --plan <name>` returns zero `subjective_judgment` entries after the rewrite lands.

### 3. State-identity defaulting

**Locked defaulting rules** (load-bearing for resume safety):

- `state.json` without a `pipeline_runtime` field → **defaults to `"legacy"`**. This is the safe default — old plans created before this sprint MUST resume on `planning.py`, not get silently re-interpreted as YAML.
- `state.json` with `pipeline_runtime: "yaml"` → resumes on YAML. If `planning.py` is also present, both paths exist; selection is via state, not flag.
- Resume command with contradictory flag (legacy state + `--use-yaml-pipeline`, or yaml state + `--use-legacy-pipeline`) → **fail loud with structured error**. Do not silently override. Operator must either pass `--force-runtime-switch` (new flag, also locked here) or let the recorded runtime win.
- `--force-runtime-switch` requires `--reason "..."` and records the switch in `state["meta"]["overrides"]`. Use case: emergency rollback when YAML path is known-broken and operator accepts the state-drift risk.

### 4. Cutover ceremony — TWO PRs, gated by `runtime-audit`

(Reduced from the original 3-PR ceremony with 14-day calendar drain.)

- **PR1**: B2 lands. Both paths exist. Default = `legacy`. `--use-yaml-pipeline` opt-in works. Tests + smoke pass.
- **PR2**: Flip default to `yaml`. `--use-legacy-pipeline` is the escape valve. PR2 includes `runtime-audit --fail-on-unsafe-cutover` as a pre-merge CI gate (catches in-flight legacy plans missing the runtime field). Both paths still alive.

**Deletion of `planning.py` is NOT in B2.** That's a separate sprint, gated by `runtime-audit` and weeks of YAML uptime. Filed as a tracking ticket.

### 5. Trace-parity, not semantic-parity

The parity gate compares the YAML path's behavior to `planning.py` on a single representative input. The gate asserts:

- **Same handler invocation order**: list of (phase_name, handler_name) tuples in execution order.
- **Same edge selection at gates**: which edge was taken at each gate stage (proceed / iterate / tiebreaker / escalate / override).
- **Same artifact paths produced**: list of `<plan_dir>/*.json|md` files written, with identical relative paths.
- **Same state transitions**: list of `state["current_state"]` values over the plan's lifetime.
- **Same `iteration` counter trajectory**: where revise loops occurred.

The gate does NOT assert:
- Identical model output text (drift on temp=0 still happens)
- Identical token counts or costs
- Identical timing
- Identical critique flag IDs (flag-ID set is non-deterministic across model retries)

**Why this is rigorous, not lazy** (per Codex review #2): with seven handlers as escape-hatches, the YAML path INVOKES THE SAME HANDLERS in the same order. The handlers' INTERNALS are unchanged. What can differ is routing (edge selection), state management, and artifact output. Trace parity tests exactly those. If trace parity passes, the YAML path is behaviorally equivalent to `planning.py` modulo handler-internal nondeterminism — which is the same nondeterminism `planning.py` already has.

### 6. One real-model smoke run

After trace-parity passes, run ONE real-model run on a representative brief (something that triggers at least one revise iteration + one gate decision; mine from `~/Documents/.megaplan-worktrees/*/.megaplan/plans/*/idea.md` if any exist OR write one fresh — verified empirically that mining produces zero candidates today, so plan on writing one).

Pass: the run reaches `state=done` and produces sensible artifacts. Manual review acceptable (not gated by automated check).

### 7. Pipeline-runtime field — owner is the YAML executor

The `pipeline_runtime` field is written by `cli.py:_handle_plan` at init (based on which flag/default was used) and `cli.py:_handle_resume` reads it to dispatch. No separate runtime-selector module — the dispatch logic lives in the `_handle_*` functions. Sprint B1's runtime-audit command independently reads the field for validation.

## Parity corpus location (lock)

The original brief said "mine `.megaplan/plans/`" but that location is gitignored and empirically empty. **Locked replacement**:

- The single representative parity input lives at `megaplan/pipelines/planning/tests/parity/representative/brief.md` (tracked in git).
- Trace-parity output (the "golden" expected trace) lives at `megaplan/pipelines/planning/tests/parity/representative/expected_trace.yaml`. Committed too.
- `tests/parity/run_parity.py` (new) runs both paths in mock-mode against the input and compares actual trace to expected trace.
- The smoke-run brief lives at `megaplan/pipelines/planning/tests/parity/smoke/brief.md`. Not in CI (real-model is too expensive); run manually before merging PR2.

## Done criteria

1. `megaplan run planning <brief>` (or `megaplan plan <brief> --use-yaml-pipeline`) succeeds end-to-end on the smoke brief, reaches `state=done`.
2. Trace-parity test in CI: YAML path matches `planning.py` on the representative input (same handler order, same edge selections, same artifact paths, same state transitions). Three consecutive runs.
3. `megaplan audit-verifiability --plan <any>` reports zero `subjective_judgment` criteria after the Phase 0 rewrite.
4. `runtime-audit --all --fail-on-unsafe-cutover` is clean before PR2 merges.
5. Existing planning tests continue passing on the legacy path (`pipeline_runtime` defaulting to `"legacy"` covers them).
6. Resume contradictions detected: legacy plan + `--use-yaml-pipeline` flag fails with structured error referencing `--force-runtime-switch`.
7. PR2 (default flip) merges; `megaplan plan` end-to-end uses YAML by default; legacy escape valve confirmed working with one regression smoke test.
8. Deferred-deletion ticket filed at `.megaplan/tickets/delete-planning-py.md` referencing this sprint and the conditions (months of YAML uptime + `runtime-audit` clean across at least 30 days).

## Touchpoints

- `megaplan/pipelines/planning/pipeline.yaml` — replaces Sprint A's parked stub. Real definition using HandlerStepSpec entries.
- `megaplan/cli.py` — `_handle_plan`, `_handle_resume`. Add `--use-yaml-pipeline` / `--use-legacy-pipeline` / `--force-runtime-switch` flags. Read/write `pipeline_runtime`.
- `megaplan/_pipeline/executor.py` — mode_overlay extraction per original brief decision #10 (still applies).
- Phase 0 criteria definitions — wherever the six current criteria are defined (probably `megaplan/data/instructions.md` or a planning-prompt file; verify during execution).
- `megaplan/pipelines/planning/tests/parity/` — new directory, parity input + expected trace + smoke brief.
- `tests/parity/run_parity.py` — new trace-parity test.
- `.megaplan/tickets/delete-planning-py.md` — new file tracking deferred deletion.

## Anti-scope

- Do NOT redesign `ParallelStage` — B1 did that.
- Do NOT delete `planning.py`. File the deferred-deletion ticket and STOP.
- Do NOT add new step kinds beyond what B1 ships.
- Do NOT build the 5-6 input real-model parity corpus from the original brief.
- Do NOT compute ±15% cost parity stats.
- Do NOT add per-run cost caps.
- Do NOT relitigate the seven-handler allowlist. An 8th handler is an escalation, not a silent addition.

## Profile recommendation

`all-codex / full / high`. Downgraded from the previous draft's `apex/thorough/high`. Apex is only warranted for the FULL behavioral migration (parity corpus + cost math + deletion ceremony). Right-sized B2 = trace parity + smoke + Phase 0 wording + runtime-selection wiring. Codex-only is enough; with the cache fix now live, the codex path runs reliably.

```bash
megaplan init .megaplan/briefs/yaml-pipelines-sprint-b2.md \
  --profile all-codex --depth high --robustness full \
  --auto-start --auto-approve \
  --in-worktree yaml-pipelines-b2 \
  --worktree-from main \
  --name yaml-pipelines-sprint-b2
```

Verify B1 has merged before kicking off — check for `_run_parallel_stage` helper and `runtime-audit` command in main.

## Sizing

Smaller than the original Sprint B brief. ~400-600 LOC of net new + changed production code. ~200-400 LOC of tests. Estimated cost (now that cache fix is live and scope is trimmed): $30-80 of harness time.
