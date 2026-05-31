# C5 Validation — Pluggable Realizer / CodeRealizer (Brief component A4 / §5)

Date: 2026-05-28. Validated against CURRENT main post the May 24–28 execute refactor
(commits `6e69814c` "M5c execute-core phase: monkeypatch migration, merge/aggregation/batch
extraction, and facade conversion" and `8f4019dd` "M6b dead-code removal").

The brief flagged this as an UNVERIFIED BET. Verdict: the bet is **partly already realized
by the refactor, partly speculative, and mis-sequenced**. Details below.

## 1. Current structure of the execute subsystem

The brief says "execute lives in `megaplan/handlers/execute/`". STALE. Reality:

- `megaplan/handlers/execute.py` (411 lines) is a **thin handler/CLI shim** — arg parsing,
  destructive-confirm gate, STATE_EXECUTED transition. 3 `is_prose_mode` call-sites, all
  CLI-policy (destructive-op confirm skip; prose post-execute state transition).
- The real subsystem is the **`megaplan/execute/` package** (3,539 LOC), produced/expanded
  by the refactor:
  - `core.py` — now **39 lines**, a pure **facade** re-exporting from siblings (was 1,930
    lines pre-refactor; the diff shows core.py shrinking by ~1,930 lines).
  - `batch.py` (1,529) — the "batch extraction": `handle_execute_one_batch`,
    `handle_execute_auto_loop`, `_run_and_merge_batch`, tier/batch-size resolution,
    blocked-task recovery, monitor hints. This is the execute engine now.
  - `merge.py` (540) — `_merge_batch_results`, `_validate_and_merge_batch`, field/value
    aliasing, reconciliation advisories.
  - `aggregation.py` (189) — `_build_aggregate_execution_payload`, scope-drift compute.
  - `quality.py` (538) — git-as-evidence quality gate, per-kind evidence checks.
  - `timeout.py` (340) — timeout checkpoint/recovery, approval-mode resolution.
  - `step_edit.py` (282) — step-level edit helper.
  - `__init__.py` (82) — re-exports the full historical name surface (back-comat).

So "facade conversion" = `core.py` became a re-export facade; "batch extraction" = the batch
loop moved into its own module. The refactor was an **internal decomposition by concern
(batch / merge / aggregation / quality / timeout)** — NOT by mode.

## 2. `is_prose_mode` branch inventory (CURRENT)

Total **20 call-site branches** across `execute/` + `handlers/execute.py` (brief claimed ~12
"in execute core"; undercount, and they are now spread across the extracted modules, not in
one core):

| File | Branches | What they gate |
|---|---|---|
| `execute/batch.py` | 5 (L289, 322, 344, 371, 1348) | Skip git snapshot + line-counts; skip `_collect_quality_deviations`; skip `_auto_attribute_unclaimed_paths`; swap evidence check to `sections_written` |
| `execute/timeout.py` | 5 (L55, 75, 82, 143, 304) | Skip git-based timeout reconciliation / execution-audit |
| `execute/aggregation.py` | 3 (L51, 57, 97) | Prose payload shape (sections vs files_changed) |
| `execute/merge.py` | 1 (L390) | `required_fields` tuple selection (see §3) |
| `handlers/execute.py` | 3 (L106, 204) | CLI destructive-confirm skip; prose post-exec transition |

Key finding: **the refactor did NOT isolate code-specific vs universal logic.** It split by
*processing stage*, leaving the prose/code fork as a cross-cutting `if is_prose_mode` inside
each stage. The code-specific machinery (git snapshot, line-count diff, quality deviations,
path auto-attribution, git-evidence checks) is exactly what the prose branches *skip*. That IS
the natural CodeRealizer surface — but it is currently scattered, not seamed.

## 3. Brief's named items — current state

- **`_merge_batch_results` two `required_fields` tuples** — CONFIRMED, now in
  `merge.py` `_validate_merge_inputs` (L390-405). Prose: `(task_id, status, executor_notes,
  sections_written)` (+`stance, stop_signal` under creative). Code: `(task_id, status,
  executor_notes, files_changed, commands_run)`. Single `if is_prose_mode` fork. This is a
  clean, small, mode-shaped seam — the cleanest evidence FOR a realizer's "merge contract".
- **`assemble_doc` (prose assembly)** — EXISTS but NOT in execute/. Lives in
  `megaplan/runtime/doc_assembly.py:199` and as a registered pipeline prompt
  (`pipelines/doc/prompts/assemble_doc.py`, `pipelines/doc/steps.py:117`). Prose assembly is
  already a **separate pipeline stage**, not an execute branch. Code mode has no analogous
  "assemble" step — git IS the artifact. This asymmetry weakens the symmetric Protocol
  (`assemble` on every backend).
- **git-as-evidence quality gate (`quality.py`)** — CONFIRMED. `quality.py` (538 lines):
  `_capture_git_status_snapshot`, `_observe_git_changes`, `_collect_execute_claimed_paths`,
  `_check_done_task_evidence_by_kind` with **per-kind dispatch and `code_*` overrides**
  (L150-192). The gate is already kind-pluggable: callers can override the `code` bucket's
  evidence shape. This is a *partial, already-built* version of the brief's `quality_gate`
  contract — but keyed on task *kind*, not on a backend object.
- **finalize verification-task injection (`handlers/finalize.py`)** — CONFIRMED, code-only.
  `_validate_finalize_payload` requires final task = test-verification **only when
  `mode == "code"`** (L277-282); `_ensure_verification_task` (L308) and
  `_ensure_user_actions_pre_gate_task` (L379, code-only L380) inject. These are explicit
  `mode == "code"` guards — more CodeRealizer-shaped logic, but in finalize, not execute.
- **`compute_task_batches` (claimed pure topo-sort → universal DAG-runner)** — CONFIRMED and
  STRONGER than the brief claims. It lives in `megaplan/_core/io.py:58`, is a pure Kahn-style
  topological sort, takes only `(tasks, completed_ids)`, has **zero mode awareness**, and
  raises on cycles. It is *already* a universal DAG primitive. The "universal DAG-runner" the
  brief wants to extract **substantially already exists** — the batching/scheduling core is
  not entangled with mode at all. What IS entangled is the per-task *execution + evidence*
  step inside `batch.py`, not the scheduler.

## 4. Does anything resembling the Realizer Protocol already exist?

No object/class named `Realizer`, no `backend_id` / `realize` / `evidence_contract`
attributes — `grep` across the repo finds none. BUT two adjacent abstractions already carry
much of the intended weight:

- **`megaplan/_core/modes.py`** — central mode predicates (`is_prose_mode`, `is_creative_mode`,
  `creative_form_id`). Every fork keys off these. This is the de-facto "backend selector",
  just expressed as functions rather than a dispatch object.
- **`megaplan/_pipeline/` package** — a *real* pluggable stage abstraction: `Pipeline`,
  `Step`, `registry.py` (`register_pipeline` / `get_pipeline`), a self-contained
  `executor.py` (walks stages, verifies declared outputs, follows labelled edges), and
  `register_pipeline_prompt(pipeline, key, renderer, mode=...)`. Doc and creative are
  first-class registered pipelines (`pipelines/doc`, `pipelines/creative`).

  CRITICAL: the pipeline layer wraps execute as a *stage* (`_pipeline/stages/execute.py:38`
  and `inprocess_step.py:259` both call `megaplan.handle_execute`). So **all modes — code,
  doc, creative — still funnel through the SAME `handle_execute` → `execute/batch.py`**, which
  then branches on `is_prose_mode` internally. The pipeline abstraction sits ABOVE execute and
  does NOT replace the in-execute mode fork. The Realizer would sit at a different level
  (inside the per-task execution step) than the pipeline registry.

## 5. ASSESSMENT (strong position)

**Is splitting along `is_prose_mode` into universal DAG-runner + CodeRealizer still the right
boundary?** — Partly mooted, partly real, but the brief's framing is off.
- The "universal DAG-runner" half is ~80% done: `compute_task_batches` (`_core/io.py`) is
  already pure and mode-free. Extracting a DAG-runner is low-value — the scheduler was never
  the entangled part.
- The genuinely mode-entangled part is the **per-task execute-and-evidence step** (git
  snapshot → run → diff/line-count → quality deviation → path attribution → evidence check),
  the five prose branches in `batch.py` plus `quality.py` + `timeout.py`'s git machinery. THAT
  cluster — "how do I run a task and prove it happened" — is the real CodeRealizer. The brief
  pointed at roughly the right code but mis-named the seam: it's an **EvidenceRealizer /
  execution-evidence backend**, not a DAG-runner split.

**Is the Realizer abstraction worth it, or YAGNI?** — As specified (5-method symmetric
Protocol: `backend_id/realize/evidence_contract/quality_gate/assemble`), it is **speculative
generality today**. Only two evidence shapes exist (git-diff vs sections_written), and they
are *asymmetric*: prose has an `assemble` step and no git evidence; code has git evidence and
no assemble. Forcing both into one symmetric Protocol invents structure that neither side
fully uses. The refactor ALSO already produced the cheaper version of two of the five methods:
`quality.py`'s `_check_done_task_evidence_by_kind` (a kind-keyed `quality_gate` with
overrides) and `merge.py`'s `required_fields` fork (an `evidence_contract`). A third backend
(e.g. a "data/notebook" or "infra" mode) would justify the Protocol — but none is on the
roadmap. **YAGNI verdict: build the seam, skip the Protocol.** Consolidate the scattered
`is_prose_mode` evidence branches into ONE injected evidence-strategy object (consuming the
already-pluggable `quality.py` per-kind hooks) — do not erect a 5-method backend Protocol with
an `assemble` method that code mode will stub.

**Correctly sequenced LAST (Body 3)?** — Sequencing it last is right for the *wrong* reason.
The brief sequences it last because it's the risky unverified bet. It should be last (or
dropped) because **the May 24–28 refactor already paid down most of its value** — the
extraction into batch/merge/quality/aggregation modules and the mode-free `compute_task_batches`
are exactly the de-risking a Realizer split would have delivered. Re-running a big mode-axis
re-org now would churn freshly-stabilized code (and tests: the refactor touched
`test_execute.py`, `test_scope_drift_doc_mode.py`, `test_receipts_drift_blocking.py`). If kept,
scope it to the narrow evidence-strategy consolidation above, NOT a backend Protocol.

## Unknown-unknowns / risks

1. **Competing abstraction collision.** The `_pipeline` registry is the project's *declared*
   extensibility seam (first-class doc/creative pipelines, `register_pipeline`). A Realizer
   inside execute would be a SECOND, lower-level pluggability axis crossing the pipeline axis.
   Two orthogonal plugin systems (pipeline-stage vs execution-backend) is an architecture smell
   the brief never reconciles. Whichever way C5 goes, it must state how Realizer relates to
   `_pipeline` — the brief is silent on the package's existence (likely also stale).
2. **`finalize.py` mode logic is OUT of scope of an execute-only Realizer.** Verification-task
   injection and `_ensure_user_actions_pre_gate_task` are `mode == "code"`-gated in
   `handlers/finalize.py`, a different handler. A "CodeRealizer" that owns code-specific
   behavior would have to reach across into finalize — the seam isn't contained in execute/.
3. **Creative is a third sub-mode under prose.** `is_prose_mode` is `{doc, joke, creative}`
   and creative adds `stance`/`stop_signal` required fields (merge.py L394). The fork is
   already 3-way in places, not binary code/prose — a 2-backend Realizer model understates the
   real branching.
