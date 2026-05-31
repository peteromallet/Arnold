# B — Completion Contract: Implementation Blast Radius

Maps everything that breaks or needs updating when terminal transitions become
fail-closed. Line numbers are current-tree (the briefs' numbers drifted slightly).

## (a) Hard-break call sites — code that trusts "done" verbatim

1. **`megaplan/auto.py:1363-1394`** — single-plan terminal stamp. `STATE_DONE`→
   `status="done"` with no evidence. *The* primary hook. Must build `CompletionContext`,
   run `MILESTONE_DONE_CONTRACT.verify`, and on `not passed` route to a non-terminal
   blocked outcome instead of returning `"done"`. Infrastructure already present:
   `_record_lifecycle_failure` (`auto.py:741`) + `latest_failure`/`resume_cursor`
   (`types.py:219-220`) — the codex brief's hook snippet drops in almost verbatim.
2. **`megaplan/auto.py:135`** — `DriverOutcome.status` literal docstring. Add
   `"verification_failed"` (or reuse `"blocked"`; `blocked` is cheaper — already wired).
3. **`megaplan/auto.py:2450-2464`** — exit-code dispatch table. If a new status is
   added it needs a code; if we reuse `"blocked"` (→5) nothing changes here.
4. **`megaplan/chain/__init__.py:1108-1110`** (`_handle_outcome`) — `status=="done"`→
   `"advance"`. This is where a verification-failed milestone must NOT advance.
5. **`megaplan/chain/__init__.py:1418-1426`** — the `state.completed.append({"status":
   outcome.status})`. Re-verify here (do not trust `outcome.status`); record the
   `CompletionReport`.
6. **`megaplan/chain/__init__.py:1211` + `1231-1243`** — `use_pr = push_enabled and
   bool(milestone.branch)` gates the entire PR/merge/done block; `merge_policy` (read at
   `1397`) is dead config because branchless milestones never reach it. Re-gate advancement
   on `report.passed`, not `bool(milestone.branch)`.
7. **`megaplan/handlers/execute.py:212-222`** — `bare` robustness writes `STATE_DONE`
   directly, no review stub, no diff check. Must run a (lighter) `EXECUTE_CONTRACT`.
8. **`megaplan/handlers/execute.py:248-272`** — non-bare review-skip path stubs
   `review_verdict:"approved"` and writes `STATE_DONE`/`STATE_AWAITING_HUMAN_VERIFY`.
9. **`megaplan/handlers/review.py:248-252` + `271`** — rework-cap force-proceed appends an
   issue then falls through to `return "success", STATE_DONE`. Per design this must force
   to **blocked/awaiting-human**, never `done`, when evidence is unsatisfied.
10. **`megaplan/handlers/review.py:235-237`** — maker-stop also returns `STATE_DONE`.
11. **`megaplan/cloud/supervise.py:403`** / **`cloud/cli.py:862-873`** — cloud operator
    treats terminal/done as advance; inherits #1/#5 verdict, no separate logic needed but
    must surface `verification_failed` rather than reporting success.

Reusable helpers to wrap (no reinvention): `validate_execution_evidence`
(`orchestration/execution_evidence.py:15`), `_capture_test_baseline`
(`handlers/finalize.py:495`, refactor into shared `run_suite`),
`_latest_execution_batch_all_tasks_done` (`chain/__init__.py:968`),
`classify_criteria` (`orchestration/verifiability.py`), `PhaseResult`/`Deviation`
(`orchestration/phase_result.py`).

## (b) Test-migration estimate — the biggest cost

**Headline: ~30-45 tests need touching; ~20-30 require a fixture that produces real
evidence (diff/green-suite/tool-calls) or a typed waiver.** Breakdown of 453 test files:

- **12 files drive the real terminal path** (`auto.drive` / `run_chain`): `test_auto.py`,
  `test_chain.py`, `test_chain_in_worktree.py`, `test_progress.py`,
  `test_auto_timestamp_staleness.py`, `test_handle_init_idea_file.py`,
  `test_core_without_cloud.py`. These are the ones that will actually flip to fail-closed.
  Most use a **fake/stub worker** (14 files match `FakeWorker`/`fake_drive`/stub harness)
  that reaches `done` with **no git diff and zero tool calls** → these FAIL `landed_diff`
  + `worker_did_work` immediately. Each fake-worker fixture needs to either write a real
  diff, or emit a typed no-op/`Waiver` artifact. Estimate **~14-20 fixtures**.
- **21 files reference `review_verdict`/`stub_review`/`"approved"`** — review-skip and
  bare-robustness tests (`test_override_strict_notes.py`, review/execute handler tests).
  Those asserting a stubbed approval reaches `done` will need a green-suite waiver or a
  real suite. Estimate **~8-12** overlap with the fake-worker set.
- **9 files import `STATE_DONE`; 88 reference the `"done"` string** — most are assertions
  on terminal *status* (cheap one-line edits: assert `blocked`+verdict, or add waiver to
  fixture), not driver-path tests. Estimate **~10-15 assertion-only edits**.

**Example failures (fail-closed):** any `test_chain.py` case using a fake driver that
returns `DriverOutcome(status="done")` with no PR/diff; `test_auto.py` bare-robustness
"reaches done" cases; review handler tests that stub `review.json` approved and expect
`STATE_DONE`. New fixtures needed: a `make_diff`/`write_noop_waiver` test helper and a
fake green-suite runner.

## (c) Legitimate-done flows needing a waiver/no-op path

- **Docs-only / prose-mode plans** (`handlers/execute.py:204-208`, `is_prose_mode`,
  `assemble_doc`) — produce a markdown diff (satisfies `landed_diff`) but no code suite →
  need `green_suite` → `not_applicable` via `docs_only` waiver in finalize.json.
- **`bare` robustness** (`execute.py:212-222`) — lighter contract: phase-coverage +
  (diff OR declared no-op); may skip review-disposition but cannot skip all evidence.
- **No-PR / `--no-push` runs** (`chain` `use_pr=False`, `MEGAPLAN_CHAIN_NO_PUSH`) —
  verification must run off working tree / commits, not PR head; today PR presence gates
  the whole block. Branchless milestone must still verify.
- **Intentionally-deferred / `deferred_human` must criteria** (`execute.py:248`,
  `review.py:261-268` → `STATE_AWAITING_HUMAN_VERIFY`) — already non-`done`; map to
  `awaiting_human`, count as satisfied via typed deferral, don't fail.
- **Genuine no-op milestone** ("already satisfied") — needs the typed `completion/noop.json`
  artifact (codex brief §6) authored by execute/finalize; without it, abandonment fails.
- **Pre-existing-red repo** — `green_suite` must diff against `baseline_test_failures`
  (`finalize.py:372`) so inherited RED isn't blamed.

## (d) Surface changes

- **`megaplan status`** (`cli/__init__.py:296-340`) — reads only `current_state`. Add the
  completion verdict / `latest_failure.kind="completion_verification_failed"` so a blocked
  plan shows *why*. `latest_failure` plumbing already exists in state.
- **`introspect`** (`observability/introspect.py:420 build_introspect_payload`, blocked
  detection `338-368`) — add `completion_verdict.json` summary + failed-evidence list;
  extend `is_blocked` recoverability hints.
- **Chain status** (`chain/__init__.py:1444`, `1812`, `_result`) — propagate
  `verification_failed`/blocked with the verifier's `failures` into the chain result JSON.
- **New artifact**: `completion_verdict.json` (atomic write per codex `completion_io.py`),
  rendered by `megaplan-observe`/introspect via the existing `Deviation` path.
- **Observability event**: add `COMPLETION_VERIFICATION_FAILED` `EventKind` alongside
  `PLAN_FINISHED` (`auto.py:1377`).
