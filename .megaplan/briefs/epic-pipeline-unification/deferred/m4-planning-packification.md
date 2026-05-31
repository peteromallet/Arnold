# m4 — Planning Pack-ification

**Epic:** pipeline-unification (`.megaplan/briefs/pipeline-unification-EPIC.md:110-118`). **Tier:** premium · thorough/high.
**Depends on:** m3 (single in-process execution path) and m1 (discovery-integrity guard, parity gate as CI).
**Grounded:** 2026-05-28, HEAD `c493f629`.

## Outcome

Planning stops being a special case. It is relocated to `megaplan/pipelines/planning/` and **discovered**
exactly like the creative/doc packs (`registry.py:360 discover_python_pipelines`) — its hardcoded
`_BUILTIN_NAMES={"planning"}` entry (`registry.py:53`) and the programmatic `register_pipeline("planning", …)`
at import time (`registry.py:420-424`) are both removed, gated behind m1's discovery-integrity guard so a
planning that fails to load is a loud error, never a silent absence. Simultaneously the **split-brain routing
collapses**: `InProcessHandlerStep._label_for`/`_gate_next_step` (`inprocess_step.py:141-200`) — the second,
independent next-step encoding running parallel to the `Pipeline` graph edges (`planning.py:85-121`) — is
retired. After m4 the graph edges are the *single* source of next-step truth. Handoff to m5: planning is a
discovered pack on the unified path; one routing source of truth; the parity gate stays green.

## Scope (tied to current file:line)

1. **Relocate planning to a pack.** Move `_pipeline/planning.py::compile_planning_pipeline` (`planning.py:24-122`)
   under `megaplan/pipelines/planning/__init__.py`, renamed to the discovery contract `build_pipeline()`
   (registry calls `builder()` with no kwargs — `registry.py:122`; cf. creative's zero-arg default
   `creative/__init__.py:93-96`). Surface module-level `description`/`default_profile`/`supported_modes`/
   `recommended_profiles` for `_module_metadata` (`registry.py:343-357`), mirroring `creative/__init__.py:40-47`.
2. **Drop the built-in.** Remove `"planning"` from `_BUILTIN_NAMES` (`registry.py:53`) and the
   `register_pipeline("planning", _planning_builder, …)` block + `_planning_builder` (`registry.py:415-424`).
   With the name gone from `_BUILTIN_NAMES`, the discovery collision-skip (`registry.py:382-389`) and the
   `read_skill_md` built-in short-circuit (`registry.py:154-155`) no longer special-case planning; planning
   may now ship its own `SKILL.md` alongside `__init__.py` (`registry.py:160-161`).
3. **Retire the parallel routing table.** `_label_for` (`inprocess_step.py:141`) and `_gate_next_step`
   (`inprocess_step.py:192`) compute `result.next` (`inprocess_step.py:78`) as a hardcoded phase→phase map
   (`prep→plan`, `plan→critique`, `critique→gate_unset:gate`, `finalize→execute`, `execute→review`,
   `gate→{gate|revise|"override force-proceed"}`). This duplicates the edges in `planning.py:85-121`. The
   executor already dispatches gate transitions on `verdict.recommendation` against `kind="gate"` edges and
   only *falls back* to `label == result.next` for normal edges (`executor.py:268-300`; mirror in
   `run_pipeline_with_policy` `executor.py:381-403`). So `_gate_next_step`'s output is already dead for gate
   dispatch (the `PipelineVerdict` wins), and `_label_for`'s remaining job is producing the bare normal-edge
   label. The collapse makes each Step emit `next` from its own outbound edge (the pack-template pattern:
   `CreativeStep` carries `next_label` as a field and returns it — `creative/steps.py:23,47`; the doc
   `AssemblyStep` returns `next='halt'` directly — `doc/__init__.py:18-21`), so next-step truth lives only on
   the graph.
4. **`prompt_key` decision (see Open questions).** Currently dead for resolution but alive for receipts +
   overlays (`s1-step-bridge.md` claim 4: `inprocess_step.run` never reads `self.prompt_key`; it *is* read by
   `StepReceipt` `receipt.py:94` and `prompt_key_overlay` `pattern_topology.py:249`). m4 must rule: graduate it
   to a real dispatch hook (the creative/doc `register_pipeline_prompt` bridge — `prompts.py:103-118`,
   `creative/prompts/__init__.py:77-109`) or remove it from the planning Steps.

## Locked decisions

- **Planning becomes a discovered package** (`pipelines/planning/__init__.py`), not a sibling file — it needs a
  `prompts/` subpackage and a `SKILL.md`, matching creative/doc layout (`registry.py:148-163`).
- **Graph edges are the single source of next-step truth.** `_label_for`/`_gate_next_step` are deleted, not
  wrapped. Gate keeps producing a `PipelineVerdict` (`inprocess_step.py:81-83`); the `kind="gate"` edges on the
  gate stage (`planning.py:64-83`) and tiebreaker stage (`planning.py:113-120`) remain the dispatch target.
- **Follow the creative/doc template, do not invent a new one** (u1: "the migration template the brief wanted
  now exists"). Reuse `register_pipeline_prompt`, the zero-arg `build_pipeline`, the module-metadata constants.
- **Parity gate is the cutover oracle.** m1's `test_pipeline_parity.py` (decision-field diff + reprompt/
  downgrade/tiebreaker branch coverage) must stay green across the relocation and the routing collapse; any
  deliberate golden change lands in its own commit (epic cross-cutting invariant, `EPIC.md:156-159`).
- **No behavior change.** The same artifacts, the same transitions, the same gate verdicts. This is a topology/
  registration refactor, not a semantics change.

## Open questions

1. **`prompt_key` — graduate or remove? (the real decision.)** Planning's production `handle_*` keep their own
   per-phase prompts and ignore the registry (`prompts.py:10-14`). Three live readers complicate a clean
   removal: `StepReceipt` audit (`receipt.py:94`) and `prompt_key_overlay` for mode-swapped pipelines
   (`pattern_topology.py:249`). Options: **(a) graduate** — wire planning prompts through
   `register_pipeline_prompt("planning", …)` so the key actually drives dispatch (matches creative/doc, unifies
   the abstraction, but duplicates prompt text the handlers already own → risk of two-prompts-drift unless the
   handler reads the registry); **(b) keep as annotation** — leave `prompt_key` as a receipt/overlay label only,
   document it as non-dispatching for handler-backed Steps; **(c) remove** from planning Steps and feed receipts/
   overlays the slot name instead. Recommend (b) for m4 (smallest, parity-safe) and defer a true (a) graduation
   to m5/m6 where the typed `HandlerContext` / Realizer makes registry-driven prompts coherent — but this is a
   plan-time decision to confirm, not a foregone conclusion.
2. **Does relocation change `__init__.py` import side-effects?** `_pipeline/planning.py` is imported lazily by
   `_planning_builder` (`registry.py:416`). The pack template imports its `prompts` subpackage for
   `register_pipeline_prompt` side-effects at module load (`creative/__init__.py:35`); if planning takes
   option (a)/(c) it inherits that ordering constraint.
3. **Thin stage wrappers (`plan.py`/`gate.py`/… `stages/*.py`) — relocate or keep in `_pipeline/stages/`?** They
   delegate to `InProcessHandlerStep` (`plan.py:23`, `gate.py:28`, etc.). Since the routing collapse changes how
   `next` is produced, decide whether the per-phase Step shells move into the pack or stay shared in `_pipeline`.

## Constraints

- **No new realization backends** (m6) and **no config-object change** (m5) — anti-scope below.
- **Depends on m3's single path existing**: the collapse is only safe once auto.py runs in-process on the
  unified executor (m3 handoff), because today `_label_for` is still load-bearing for the InProcess test path.
- **Discovery-integrity guard (m1) must be in place** before dropping `_BUILTIN_NAMES` — otherwise a planning
  that fails to import becomes a silent "no pipeline named 'planning'" (`registry.py:118-121`), the exact
  failure mode the guard exists to prevent.
- Honor the existing collision/precedence rules in `_scan_dir_for_pipeline_modules` (`registry.py:259-298`):
  a `planning/` package directory must not be shadowed by any sibling `planning.py`.
- The cloud supervisor SSHes into internal imports; planning's relocation must not break the `megaplan status`
  contract m1 pinned, nor any `from megaplan...` import the supervisor reaches (EPIC #9, `EPIC.md:55-58`).

## Done criteria (testable)

1. `megaplan/_pipeline/planning.py` no longer exists (or is a thin re-export shim, decided at plan time);
   `compile_planning_pipeline` logic lives at `megaplan/pipelines/planning/__init__.py::build_pipeline`.
2. `grep _BUILTIN_NAMES megaplan/_pipeline/registry.py` shows it empty/removed; `register_pipeline("planning"…)`
   is gone; `registered_pipelines()` still returns `"planning"` **via discovery** (assert in a test).
3. `_label_for` and `_gate_next_step` are deleted from `inprocess_step.py`; `grep` across `megaplan/` + `tests/`
   finds no callers. Next-step truth is asserted to come only from graph edges.
4. **Parity gate green**: `test_pipeline_parity.py` (decision-field diff + reprompt/downgrade/tiebreaker
   branches) passes unchanged — direct `handle_*` vs the relocated discovered pipeline produce byte-identical
   artifacts and identical state transitions.
5. The `prompt_key` decision is implemented and tested: if graduated, a planning prompt resolves via
   `register_pipeline_prompt`; if kept-as-annotation, a test asserts receipts/overlays still carry the key and
   dispatch ignores it.
6. A discovery-integrity test asserts planning compiles and is discoverable (m1 guard exercised for planning).
7. The five tests that import `build_inprocess_planning_steps`/`build_revise_step`/`build_review_step`
   (`test_pipeline_parity.py:32`, `test_pipeline_resume.py:26`, `test_pipeline_planning_e2e.py:27`,
   `characterization/test_pipeline_golden.py:37`) and `test_pipeline_typed_edges.py:148` still pass (updated for
   the collapsed routing where they assert `_label_for` behavior).
8. Full suite + `test_import_surface.py` characterization stays green; no new import cycles.

## Touchpoints

- **Core:** `megaplan/_pipeline/registry.py` (53, 154-155, 382-389, 415-424); new
  `megaplan/pipelines/planning/__init__.py` + `prompts/` + `SKILL.md`; delete/shim `megaplan/_pipeline/planning.py`.
- **Routing collapse:** `megaplan/_pipeline/stages/inprocess_step.py` (78, 141-200); the thin shells
  `stages/{plan,gate,prep,critique,revise,finalize,execute,review,tiebreaker}.py` and the helper builders
  `build_inprocess_planning_steps`/`build_revise_step`/`build_review_step` (`inprocess_step.py:232-282`).
- **Edge dispatch (read-only, must keep working):** `megaplan/_pipeline/executor.py` (262-300, 381-403).
- **prompt_key readers:** `_pipeline/receipt.py:94`, `_pipeline/pattern_topology.py:249`, `_pipeline/prompts.py`.
- **Template references (do not modify):** `megaplan/pipelines/creative/`, `megaplan/pipelines/doc/`.
- **Tests:** the five parity/resume/e2e/golden/typed-edge tests listed above.

## Anti-scope

- **No new realization backends** (EvidenceRealizer/CodeRealizer, PR #43) — that is m6 (`EPIC.md:132-141`).
- **No config-object change** — `HandlerContext`/`args_to_hctx` is m5 (`EPIC.md:120-130`); handlers keep the
  `argparse.Namespace` contract (`inprocess_step.py:50-72`).
- **No execution-model change** — m3 already moved auto.py in-process; m4 assumes that path, does not alter it.
- **No planning prompt-content rewrite** — relocating prompt modules ≠ editing their text (mirrors m2's
  "does not touch planning's own profile content").
- **No new pipeline branches / topology change** — same prep→plan→critique→gate→…→review shape (`planning.py:33-39`).
