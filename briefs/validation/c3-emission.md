# C3 — Observability / Emission Validation (vs current code, 2026-05-28)

Brief dated 2026-05-23; subsystem refactored May 24–28. Verified against current code.

## Brief premise
"Emission is load-bearing (hazard 2 / F4 foundation), and the executor currently emits NOTHING."
**Premise is largely FALSE against current code.** Both `execute` and `review` handlers call
`set_active_step` AND emit `phase_result.json` and receipts inline. The architecture the brief
proposes ("single shared post-step emission hook") already substantially exists.

## Claim 1 — `_emit_phase_result` only reached via InProcessHandlerStep → _finish_step; executor emits zero
**FALSE (current code).**
- `_emit_phase_result` defined at `megaplan/orchestration/phase_result.py:504`.
- It is called from **three** sites, NOT only `_finish_step`:
  - `megaplan/handlers/shared.py:453` — `_finish_step` (covers prep/critique/gate/finalize/revise — the
    planning phases driven through `InProcessHandlerStep`).
  - `megaplan/handlers/execute.py:306` — the **execute handler itself**, after the dispatcher loop,
    keyed off `response["_phase_outcome"]`.
  - `megaplan/handlers/review.py:469` — the **review handler itself**.
- `phase_result_guard` (phase_result.py:562) also emits an error-result on exception, wrapped around the
  execute body at `execute.py:160`.
- `_finish_step` (shared.py:380) explicitly **skips** receipt emission for `execute`/`review`
  (shared.py:441 `if step not in {"execute","review"}`) because those phases emit their own.
- `InProcessHandlerStep` is real (`megaplan/_pipeline/stages/inprocess_step.py:26`) and wraps handlers,
  but execute/review do not depend on `_finish_step` to emit.

## Claim 2 — receipts/ is LOAD-BEARING; `_pipeline/receipt.py` is DORMANT (audit INVERTED the brief)
**TRUE — the later audit is correct.**
- `megaplan/receipts/` is wired into production. `build_receipt`/`write_receipt` called from:
  - `megaplan/handlers/shared.py:363,375` (via `_emit_receipt`, for planning phases)
  - `megaplan/execute/batch.py:711/724` and `:1445/1458` (execute receipts, inline)
  - extractors/drift used by `megaplan/execute/aggregation.py:20`
  - query/report consumed by `megaplan/cli/status_view.py:908,912` (`megaplan audit`)
- Receipts have their own `schema_version` (`receipts/schema.py:25`, default `1` at `receipts/__init__.py:88`).
- `megaplan/_pipeline/receipt.py` (`ReceiptDecorator`, "Sprint 5 Chunk D") has **ZERO importers** outside
  itself. `grep ReceiptDecorator` across the tree returns only its own definition. **Confirmed dormant.**

## Claim 3 — `_emit_phase_result` depends on `meta.current_invocation_id` set by `set_active_step`, and the executor never calls `set_active_step`
**Dependency TRUE; "executor never calls set_active_step" FALSE.**
- `_emit_phase_result` reads `state["meta"]["current_invocation_id"]` (phase_result.py:527). If absent it
  **logs a warning and skips emission** (phase_result.py:528–539) — it does NOT raise (brief's docstring
  claim of `RuntimeError` is stale; the code degrades gracefully).
- `current_invocation_id` is set by `set_active_step` (`_core/state.py:677`, sets key at `state.py:716`).
- The execute handler **does** call `set_active_step` at `execute.py:155`; review at `review.py:551`;
  batch dispatch also calls it (`execute/batch.py:548,1132`). So the gap the brief describes does not exist
  on the production path. It only manifests in tests that mock `_run_worker` at module level (the warning
  branch's documented case).

## Claim 4 — auto.py picks next phase from status (state.json/next_step), not phase_result.json; success-synthesis fallback exists
**BOTH TRUE.**
- Driver loop reads `next_step = status.get("next_step")` (`auto.py:1291`), where `status` comes from
  `megaplan status` (`auto.py:466 _status` → `_run_megaplan(["status",...])`). Phase selection is
  state-driven, not phase_result-driven.
- `phase_result.json` is read only as a **secondary outcome signal** and only when its mtime/size signature
  changed for the just-run phase (`auto.py:1130,1154–1158`, `_phase_result_signature` at :731).
- Success-synthesis fallback on clean exit with no phase_result: `auto.py:1185–1193` — `code == 0` →
  synthesize `PhaseResult(exit_kind=success, invocation_id="synthesized")`. Comment notes this now only
  fires for "legacy plans and test mocks" since all handlers emit. Timeout/idle/context-exhaustion also
  synthesized (:1164–1181).

## Claim 5 — consumers map
- **status command** (`cli/status_view.py`): reads `phase_result.json` via `read_phase_result` for
  blocked-task/deviation recovery inputs (:231–240,294); hosts `megaplan audit` → receipts query/report
  (:904–914).
- **auto driver** (`auto.py`): reads status JSON for next_step; reads phase_result as outcome signal.
- **chain** (`megaplan/chain/__init__.py`): drives plans via `_drive_plan` → `megaplan.auto` (:65,909);
  consumes the driver's terminal status + its own `chain_state.json` (:523,547). Indirect phase_result
  consumer through the driver.
- **cloud** (`cloud/cli.py`): fetches remote `megaplan status` JSON and `chain_state.json`
  (:78–90,199–224,778). Consumes status, not phase_result directly.
- **introspect** (`observability/introspect.py`): reads `state.json` (:202–203). Not phase_result/receipts.
- **doctor** (`observability/doctor.py`): reads `state.json` (:259,404). Not phase_result/receipts.
- Receipts also read by `receipts/report.py` (audit reporting) and `cli/resolutions.py`,
  `handlers/override.py` read phase_result.

## ASSESSMENT
A single shared post-step emission hook owned by the executor, called on both the InProcessHandlerStep
planning path and the execute/review handler path, IS the right target shape — but it is a
**consolidation/dedup refactor, not a from-zero foundation**: emission is already present on every
production path (three `_emit_phase_result` sites + two receipt sites), just duplicated and divergent
(execute/review hand-roll outcome→exit_kind and receipt construction; `_finish_step` does it generically
but excludes execute/review). Whether it must land BEFORE handler migration: NO, not as a precondition —
emission won't silently vanish because each handler emits for itself today; but consolidating it first is
**advisable** so the migration has one emission contract to honor instead of three. If the executor became
the single path WITHOUT first unifying emission, the silent breakage risk is: (a) execute/review's inline
`_phase_outcome`→exit_kind mapping and inline receipt-with-drift logic would be lost if the generic
`_finish_step` path (which skips execute/review) became the only emitter — phase_result would degrade to
plain success/error and execute receipts would lose drift/metrics; (b) if `set_active_step` is dropped on
the new path, emission silently no-ops (warns + skips, no crash — Claim 3), so loss would be invisible
until someone reads `audit`/status.

## Unknown-unknown
`auto.py:1187` comment asserts "all 8 handlers now emit," but I verified emission directly only for
execute, review, and the `_finish_step`-routed planning phases. The `feedback` phase emits via
`cli/feedback.py:432,477` (separate site, outside the executor/handlers). Worth confirming every phase in
`PHASE_NAMES` has a live emission site before relying on the synthesis fallback being "legacy/test only" —
a phase that exits 0 without emitting would be silently synthesized as success, masking real outcome data.
