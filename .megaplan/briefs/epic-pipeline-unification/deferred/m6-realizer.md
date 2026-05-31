# m6 — Realization backends: EvidenceRealizer + re-home PR #43

**Epic:** Pipeline Unification (`.megaplan/briefs/pipeline-unification-EPIC.md`, m6 §132–141, validation-change #7 §49–51).
**Tier:** premium · thorough/high. **Depends on:** m5 (config substrate / `HandlerContext`). **Benefits from:** m4 (planning pack-ified; single routing source).
**Grounded:** 2026-05-28 against current main. **Definitive findings:** `.megaplan/briefs/validation/c5-realizer.md`, `.megaplan/briefs/validation/c7-pr43.md`.

---

## Outcome

megaplan stops forking execution-evidence behavior on ad-hoc `is_prose_mode` checks scattered through the execute subsystem and `finalize`, and instead **injects a single evidence/realization strategy** selected once per run. "How a pipeline proves its work happened" (git snapshot → diff → line-count → quality deviation → path attribution → evidence-shape check for code; assembled sections for prose) becomes one named, swappable object — the **EvidenceRealizer** — rather than ~20 in-line branches. `finalize` becomes mode-agnostic (its three `mode == "code"` / `mode in {doc,joke}` guards delegate to the realizer). Packs declare a `capabilities: tuple[str, ...]` metadata tuple; `patterns.py` is formalized as the named capability library. PR #43's `worktrees/` package is re-homed and its execute integration re-implemented against main's batch contract, landing **CodeRealizer** as the first concrete realizer — first-among-equals, not a privileged default.

**Handoff:** pluggable realization backends; planning ships CodeRealizer; a prose realizer covers doc/joke/creative; the seam is documented as the extension point for a future third backend.

---

## Scope (tied to current file:line)

1. **DAG-runner boundary — mostly already exists; formalize, don't rebuild.** `compute_task_batches` (`megaplan/_core/io.py:58`) is a pure Kahn topo-sort taking only `(tasks, completed_ids)`, with **zero mode awareness**, raising on cycles (`io.py:99`). `split_oversized_batches` (`io.py:107`) is likewise mode-free. Per c5 §80–86 this is already a universal DAG primitive (~80% done). m6 scope here is **naming/boundary documentation + ensuring the realizer never re-implements scheduling**, not extraction.

2. **Consolidate the 20 `is_prose_mode` branches into an injected EvidenceRealizer.** Inventory (c5 §36–48, re-verified):
   - `megaplan/execute/batch.py` — L289 (skip git snapshot + before-line-counts), L322 (skip `_collect_quality_deviations`), L344 (skip `_auto_attribute_unclaimed_paths` + `_observe_git_changes`), L371 (swap evidence check to `sections_written`), L1348.
   - `megaplan/execute/timeout.py` — L55, L75, L82 (skip git-based timeout reconciliation / execution-audit), L143, L304.
   - `megaplan/execute/aggregation.py` — L51, L57, L97 (prose payload shape: `sections_written` vs `files_changed`).
   - `megaplan/execute/merge.py` — L390 (`required_fields` tuple fork; code = `(task_id,status,executor_notes,files_changed,commands_run)`, prose = `…sections_written`, creative adds `stance,stop_signal` at L394–397).
   - `megaplan/handlers/execute.py` — L106 (destructive-confirm skip), L204 (prose post-exec `STATE_EXECUTED` transition).
   These collapse into a strategy object with the methods the branches actually need (see Locked decisions for the exact, asymmetric surface).

3. **Make `finalize` mode-agnostic.** `megaplan/handlers/finalize.py` has the code-only injection cluster: `_validate_finalize_payload` requires a final test-verification task only when `mode == "code"` (L276–282); `_ensure_verification_task` (L308) + `_ensure_user_actions_pre_gate_task` (L379, early-returns unless `mode == "code"` at L380) are invoked at L604–605, inside the `_write_finalize_artifacts` `else` branch whose `if` handles `mode in {"doc","joke"}` baseline-skip (L597–605). These delegate to the realizer (`realizer.finalize_tasks(payload, state)` / `realizer.baseline(...)`), so finalize stops branching on the mode string.

4. **Declarative `capabilities` pack metadata + formalize `patterns.py`.** `_module_metadata` (`megaplan/_pipeline/registry.py:343`) currently surfaces `description`, `default_profile`, `supported_modes`, `recommended_profiles`. Add a `capabilities: tuple[str, ...]` key read the same way (L351-style block) and expose it via `PipelineRegistry.metadata` / `pipeline_metadata()` (`registry.py:197`). `patterns.py` (`megaplan/_pipeline/patterns.py`) is already a compatibility facade re-exporting from `pattern_topology` / `pattern_dynamic` / `pattern_joins` / `pattern_types`; formalize its `__all__` as the named capability vocabulary that `capabilities` values reference. **No re-split** (already done by hardening epic).

5. **Re-home PR #43 (CodeRealizer vehicle).** Per c7: PR is CLOSED, recoverable at `4ef36402` via `refs/pull/43/head` (object already in local DB, c7 §53). **Lift** `megaplan/worktrees/` (9 modules: `identity, integration, lifecycle, patches, recovery, registry, report, secrets, paths`) ~intact — absent on main, low-conflict (c7 §41, §67). **Re-implement** the execute integration (`execute/core.py` graft, `execute_resume_cursor.py`, `migration*.py`) against main's batch / `current_state` contract — the old per-task artifact wiring is dead-on-arrival (c7 §68). Treat the branch's `core.py` diff as a design spec, not patchable code. **Port** the ~18 crash-injection/custody/patch-validation test files as behavioral specs, re-pointed at new module paths (c7 §69).

---

## Locked decisions

- **EvidenceRealizer SEAM, not a symmetric 5-method Protocol.** Per c5 §110–136: only two evidence shapes exist (git-diff vs `sections_written`) and they are **asymmetric** — prose has an `assemble` step (`megaplan/runtime/doc_assembly.py:199`, a registered pipeline stage `pipelines/doc/steps.py:117`) and no git evidence; code has git evidence and **no** assemble (git IS the artifact). A symmetric `backend_id/realize/evidence_contract/quality_gate/assemble` Protocol would force code to stub `assemble`. **Build the seam:** a realizer whose surface is the *union of what the branches actually call* — roughly `capture_pre_state`, `collect_evidence_deviations`, `required_fields`, `check_done_evidence`, `finalize_tasks`, plus prose-only `assemble`. Methods absent for a mode are no-ops, not stubs of a forced symmetry.
- **Reuse the already-pluggable hooks; don't re-erect them.** `quality.py::_check_done_task_evidence_by_kind` (`megaplan/execute/quality.py:150`) is already a kind-keyed quality gate with `code_*` overrides (L182–190) — the realizer's `check_done_evidence` *consumes* it, it does not replace it. `merge.py`'s `required_fields` fork (L390–405) becomes `realizer.required_fields(state)`.
- **Realizer-vs-pipeline-axis reconciliation (the architecture smell c5 §149 flags).** Two plugin axes coexist and are **explicitly orthogonal**:
  - **Pipeline/pack axis** (`_pipeline/registry.py`, `register_pipeline`, discovered `pipelines/*`): chooses *which stages run and in what topology* (prep→plan→…→review). Doc/creative are first-class registered pipelines.
  - **EvidenceRealizer axis** (this milestone): chooses *how the per-task execute step proves work*, one level below the pipeline graph. c5 §101–108 confirms ALL modes funnel through the same `handle_execute → execute/batch.py`, which then branches internally — the pipeline layer sits *above* execute and does not replace the in-execute fork. The realizer replaces that fork.
  - **Binding rule:** a pack does not pick a realizer imperatively. The realizer is **derived from pack `capabilities`** (e.g. `"git-evidence"` → CodeRealizer; `"prose-assembly"` → ProseRealizer), resolved once at execute entry from `pipeline_metadata(name)` + `state["config"]["mode"]`. This keeps one selection point and prevents a pack from declaring stage topology and evidence strategy as two independently-drifting facts.
- **CodeRealizer is first-among-equals.** Planning ships it; it is selected by capability, not hardcoded as the fallback. The mode default (`is_prose_mode` → `mode in {doc,joke,creative}`, `_core/modes.py:38`) maps to ProseRealizer; everything else maps to CodeRealizer.
- **PR #43: re-implement, do NOT rebase** (c7 §62–71). Pin `4ef36402` as reference. ~30% lift (`worktrees/`), ~70% re-implement (execute integration). Acceptance contract = the **5 failing `tests/test_auto.py` cases** (c7 §21): `test_plan_liveness_mtime_uses_state_and_execution_batches`, `test_execute_callback_failure_reconciles_latest_batch_and_clears_active_step`, `test_failed_execute_callback_resume_restores_executed_state`, `test_failed_execute_callback_resume_restores_blocked_execute_to_finalized`, `test_worker_blocked_after_max_retries_emits_terminal_status`.

---

## Open questions

1. **Is a real 3rd mode coming?** c5 §133 says none is on the roadmap (a "data/notebook" or "infra" mode would justify a Protocol; nothing exists). The seam must be cheap to extend but we do **not** speculatively build for #3. **Decision needed in-plan:** confirm with Peter no 3rd evidence shape is imminent; if one is, re-evaluate whether the union-surface seam should harden toward a Protocol.
2. **How does a 3rd mode cross the pipeline axis?** If a future "infra/apply" realizer (e.g. terraform plan/apply as evidence) appears, does it ride an existing pack via a new `capabilities` value, or does it need its own pipeline topology? The capability-derives-realizer binding (above) is designed so a 3rd shape is *just a new capability string + a new realizer class*, with the pipeline graph unchanged — validate this holds.
3. **Creative is a 3-way sub-mode of prose** (c5 §163; `is_prose_mode = {doc,joke,creative}`, `_core/modes.py:38`; creative adds `stance/stop_signal` required fields at `merge.py:394`, and `aggregation.py:101` fires creative checks). Does ProseRealizer carry a creative sub-variant internally, or is creative its own realizer? Lean: ProseRealizer handles the doc/joke/creative `required_fields` variance internally (it is already one `is_prose_mode` branch with a nested `is_creative_mode`), avoiding a 4th class.
4. **`handlers/execute.py:204` prose state transition** — is the post-`STATE_EXECUTED` prose transition a CLI-policy concern (stays in the handler) or a realizer concern? Lean: stays CLI-policy; the realizer owns evidence, not state-machine transitions.

---

## Constraints

- **m1 parity gate stays green** (epic cross-cutting invariant §156–159). Any change to observable planning/finalize behavior updates golden expectations deliberately, in its own commit. This is a **pure refactor** — behavior must be byte-identical for code and prose runs before/after consolidation.
- **Depends on m5 substrate.** The realizer is injected via `HandlerContext` services (m5 handoff: `handle_*(root, state, hctx)`), not threaded as a new positional arg. If m5 is incomplete, the realizer is selected at execute entry and passed down through the existing call chain as a stopgap — but the home is `hctx`.
- **No churn of freshly-stabilized code beyond the seam** (c5 §138–145). The May 24–28 refactor (`6e69814c`, `8f4019dd`) split `core.py` → facade + `batch/merge/aggregation/quality`. Do not re-org by mode; consolidate the branches *in place* into a strategy the existing modules consume.
- **External coupling:** the cloud supervisor SSHes internal imports and there are 26 ambient `MEGAPLAN_*` env reads (epic §55–58). Adding a realizer must not change the `megaplan status` JSON contract pinned in m1.

---

## Done criteria (testable)

1. A single `EvidenceRealizer` selection point exists; **zero `is_prose_mode` / `mode == "code"` / `mode in {doc,joke}` branches remain in `execute/batch.py`, `execute/timeout.py`, `execute/aggregation.py`, `execute/merge.py`, `handlers/finalize.py`** for evidence/realization concerns (grep is the gate; CLI-policy branches in `handlers/execute.py` may remain per Open Q4, documented).
2. CodeRealizer and ProseRealizer both pass the m1 parity gate; a full code run and a full doc run produce byte-identical artifacts vs pre-m6 main.
3. `pipeline_metadata("planning")["capabilities"]` returns a non-empty tuple; a discovered pack declaring `capabilities` surfaces it through `_module_metadata` (`registry.py:343`); a test asserts capability → realizer resolution.
4. `megaplan/worktrees/` package present, imports clean, its lifted tests pass.
5. The **5 `tests/test_auto.py` cases** (c7 §21) pass against the re-implemented execute integration.
6. Ported crash-injection/custody/patch tests (~18 files, re-pointed) pass as CodeRealizer behavioral specs.
7. A realizer-selection unit test proves: `mode=code` → CodeRealizer, `mode in {doc,joke,creative}` → ProseRealizer, capability override wins.

---

## Touchpoints

- `megaplan/execute/batch.py` (L289, 322, 344, 371, 1348), `timeout.py` (L55, 75, 82, 143, 304), `aggregation.py` (L51, 57, 97), `merge.py` (L390–405), `quality.py:150` (`_check_done_task_evidence_by_kind` — consumed, not rewritten).
- `megaplan/handlers/finalize.py` (L276–282, 308, 379, 597–605), `handlers/execute.py` (L106, 204 — CLI-policy, likely retained).
- `megaplan/_core/io.py:58` (`compute_task_batches` — documented boundary, untouched), `megaplan/_core/modes.py:38` (mode→realizer mapping source).
- `megaplan/runtime/doc_assembly.py:199` (`assemble_doc` — ProseRealizer's `assemble`), `pipelines/doc/steps.py:117`.
- `megaplan/_pipeline/registry.py:343` (`_module_metadata` + `capabilities`), `registry.py:197` (`pipeline_metadata`), `megaplan/_pipeline/patterns.py` (capability library facade).
- New: `megaplan/worktrees/*` (lifted from `4ef36402`), realizer module (likely `megaplan/execute/realizer.py` or `megaplan/realization/`).
- m5 `HandlerContext` (realizer injection home). `tests/test_auto.py` (acceptance), ported `tests/test_worktree*`/crash-injection suite.

---

## Anti-scope

- **Do NOT re-extract `patterns.py`** — already split into `pattern_topology/dynamic/joins/types`; only formalize `__all__` as the capability vocabulary.
- **Do NOT re-decompose `execute/core.py`** — already a facade over `batch/merge/aggregation/quality/timeout` (hardening epic).
- **Do NOT extract a new DAG-runner** — `compute_task_batches` is already pure and mode-free; document the boundary, don't move it.
- **Do NOT build a symmetric 5-method Realizer Protocol** with a code-stubbed `assemble` (c5 YAGNI verdict §136).
- **Do NOT rebase PR #43** — re-implement against the batch contract (c7 §62).
- **No execution-model changes** (m3 owns auto-in-process), **no config-object changes** (m5 owns `HandlerContext`), **no pack relocation** (m4 owns planning pack-ification). m6 consumes those handoffs.
