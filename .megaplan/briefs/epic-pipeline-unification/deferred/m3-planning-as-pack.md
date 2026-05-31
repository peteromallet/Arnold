# m3 — Planning as a discovered pack

**Epic:** pipeline-unification (`.megaplan/briefs/pipeline-unification-EPIC.md:78-87`). **Tier:** premium · thorough/high.
**Depends on:** m1's executor merge (`run_pipeline` + `run_pipeline_with_policy` → one override-complete path) and m1's discovery-integrity guard (report-loud user packs, fail-loud in-tree). **Does NOT depend on the deferred auto.py in-process port** — see Constraints.
**Grounded:** 2026-05-28, HEAD `c493f629`. Authoritative scope: EPIC m3 section + premortem `p1-blast-radius.md` #4 (the THIRD encoding the v1 plan missed).

## Outcome

Planning stops being a privileged built-in and becomes a pack **discovered** exactly like `creative/` and `doc/`
(`registry.py:360 discover_python_pipelines`). Its hardcoded `_BUILTIN_NAMES={"planning"}` (`registry.py:53`) and the
import-time `register_pipeline("planning", _planning_builder, …)` (`registry.py:415-424`) are both removed, gated behind
m1's discovery-integrity guard so a planning that fails to load is a loud error, never a silent
"no pipeline named 'planning'" (`registry.py:118-121`).

Simultaneously **all THREE next-step encodings collapse onto the `Pipeline` graph edges as the single source of truth**:
1. `InProcessHandlerStep._label_for` (`inprocess_step.py:141`) — the per-phase normal-edge label.
2. `InProcessHandlerStep._gate_next_step` (`inprocess_step.py:192`) — the gate-rec→bare-step map.
3. `_core/workflow.py::workflow_next` / `infer_next_steps` (`workflow.py:282-302`) — the **robustness-transition graph**
   the v1 plan missed, consumed by override (9 action handlers), `status.next_step`, doctor, introspect, and ~10 more sites.

The v1 draft (`deferred/m4-planning-packification.md`) named only (1)+(2). p1-blast-radius #4 confirmed (3) feeds the entire
override/status/doctor/introspect surface and will silently desync if left as a parallel map. m3 reconciles it.

Handoff to m4: planning is a discovered pack on the unified path; one routing source of truth that the shared emission/
evidence kernels can read.

## Scope (tied to current file:line)

1. **Relocate planning to a pack.** Move `compile_planning_pipeline` (`planning.py:24-122`) under
   `megaplan/pipelines/planning/__init__.py`, renamed to the discovery contract `build_pipeline()` (zero-arg, like
   `creative/__init__.py:93-96` and `doc/__init__.py:66`). Surface module-level
   `description`/`default_profile`/`supported_modes`/`recommended_profiles` for `_module_metadata` (`registry.py:343-357`),
   mirroring `creative/__init__.py:40-47`. Planning may now ship its own `SKILL.md` alongside `__init__.py`
   (`registry.py:160-161`); the prompt subpackage (if `prompt_key` is graduated — see Open questions) lands at
   `pipelines/planning/prompts/`.

2. **Drop the built-in.** Remove `"planning"` from `_BUILTIN_NAMES` (`registry.py:53`) and the
   `register_pipeline("planning", …)` block + `_planning_builder` (`registry.py:415-424`). With the name gone, the
   discovery collision-skip (`registry.py:382-389`) and the `read_skill_md` short-circuit (`registry.py:154-155`) stop
   special-casing planning. Honor `_scan_dir_for_pipeline_modules` precedence (`registry.py:259-298`): a `planning/`
   package must not be shadowed by any sibling `planning.py`. `registered_pipelines()` must still return `"planning"`
   **via discovery** (assert in a test).

3. **Collapse encodings (1)+(2) — `_label_for` / `_gate_next_step`.** These compute `result.next` (`inprocess_step.py:78`)
   as a hardcoded phase→phase map that duplicates the edges in `planning.py:85-121`. The executor already dispatches gate
   transitions on `verdict.recommendation` against `kind="gate"` edges and only *falls back* to `label == result.next`
   for normal edges (`executor.py:268-300`; mirror in the now-merged single path from m1). So `_gate_next_step`'s output is
   already dead for gate dispatch (the `PipelineVerdict` wins, `inprocess_step.py:81-83`), and `_label_for`'s only live job
   is the bare normal-edge label. Collapse so each Step emits `next` from its own outbound edge — the pack-template pattern:
   `CreativeStep` carries `next_label` as a field (`creative/steps.py`, `creative/__init__.py:74-80`); the doc `AssemblyStep`
   returns `next='halt'` directly (`doc/__init__.py:18-21,107-111`). After this, next-step truth for the in-process walk lives
   only on the graph; `_label_for`/`_gate_next_step` are deleted, not wrapped.

4. **Reconcile encoding (3) — `workflow_next`.** THE hard part. `workflow_next` (`workflow.py:282-302`) is **not** a static
   restatement of the graph edges. It computes the next steps from `_workflow_for_robustness(...)` — a per-call merge of
   `WORKFLOW` with `_ROBUSTNESS_OVERRIDES` keyed on `robustness × creative × with_prep × with_feedback`
   (`workflow.py:184-209`) — then filters each transition through `_transition_matches` (`workflow.py:212-242`, gate-condition
   predicates over `state["last_gate"]`) and appends a synthetic `"step"` pseudo-target when `current_state ∈
   _STEP_CONTEXT_STATES` (`workflow.py:49-54, 297-298`). Its ~15 consumers read it as the **valid-next-actions** surface, not
   the pipeline's literal edge: `cli/status_view.py:748` (the `next_step` field cloud reads), `handlers/override.py`
   (9 `infer_next_steps`/`workflow_next` calls feeding `valid_next=`), `handlers/shared.py:437,476,531,571`,
   `handlers/gate.py:161`, `handlers/init.py:472`, `execute/step_edit.py:117,195,224,257`, `observability/introspect.py:375`
   (`recoverable_via`), `observability/doctor.py:426`. m3 must make these read the graph (the single source of truth) rather
   than a parallel hand-maintained map — **or** pin `workflow_next` as the canonical label source and route the graph through
   it. Either direction, the acceptance is: `status.next_step`, the override `valid_next`, doctor's `recoverable`, and the
   graph cannot disagree. See Open questions for whether full equivalence is even achievable this milestone.

5. **`prompt_key` decision.** Currently dead for handler dispatch but alive for receipts (`receipt.py:94`) and overlays
   (`pattern_topology.py:249`) — `inprocess_step.run` never reads `self.prompt_key` (s1-step-bridge claim 4). Rule it
   per the locked decision below.

## Locked decisions

- **Planning becomes a discovered package** (`pipelines/planning/__init__.py`), not a sibling file — it needs a `SKILL.md`
  and (if `prompt_key` graduates) a `prompts/` subpackage, matching the creative/doc layout.
- **Graph edges are the single source of next-step truth** for the in-process walk. `_label_for`/`_gate_next_step` are
  deleted. Gate keeps emitting a `PipelineVerdict`; the `kind="gate"` edges on the gate stage (`planning.py:64-83`) and
  tiebreaker stage (`planning.py:113-120`) remain the dispatch target.
- **`prompt_key` stays a receipt/overlay annotation (option b)** — non-dispatching for handler-backed Steps, documented as
  such; a test asserts receipts/overlays still carry the key and dispatch ignores it. A true `register_pipeline_prompt`
  graduation (option a) is deferred to m4-era work where the shared dispatch service makes registry-driven prompts coherent.
  Default per EPIC m3 ("default keep-as-annotation"); confirm at plan time, do not foreclose.
- **Follow the creative/doc template; do not invent a new one** — zero-arg `build_pipeline`, module-metadata constants,
  per-Step `next_label`. (u1: the migration template the brief wanted already exists.)
- **Parity gate is the cutover oracle** and stays green across the relocation, the (1)+(2) collapse, and the (3)
  reconciliation. Any deliberate golden change lands in its own commit (EPIC cross-cutting, `EPIC.md:134-135`).
- **No behavior change** to transitions, artifacts, or gate verdicts. This is a topology/registration/routing-source
  refactor, not a semantics change.

## Open questions

1. **Is `workflow_next` actually equivalent to the static graph edges? (Likely NOT — resolve at plan time.)** The graph
   (`planning.py`) is a single fixed topology. `workflow_next` is a *function of mutable state*: it re-derives transitions
   per call from robustness × creative × with_prep × with_feedback, filters on live `last_gate` predicates, and appends a
   synthetic `"step"`. So `workflow_next` encodes (i) robustness-conditional edge presence (light/bare drop gate/review —
   `workflow.py:172-181, 207`), (ii) gate-recommendation branching as state predicates, (iii) the `"step"` pseudo-action, and
   (iv) creative/feedback rewiring. The static planning graph has none of (i)/(iii)/(iv) baked in. **Decision needed:** does
   m3 (a) make `workflow_next` *derive its candidate edges from the graph* and keep the predicate/robustness filtering as a
   thin layer over it (graph = topology source, `workflow_next` = state-aware projector), or (b) accept that `workflow_next`
   is a distinct "valid-actions" concern and the "single source of truth" claim applies only to the *executor's* next-step
   (encodings 1+2), with `workflow_next` reconciled by deriving from the same edge set rather than a hand-kept dict? Default
   recommendation: (a)-flavored — the graph is the topology of record; `workflow_next` keeps the robustness/predicate/`"step"`
   projection but enumerates candidates *from the pack's edges*, not from the parallel `WORKFLOW` dict. This must be proven,
   not assumed; if the robustness overrides cannot be expressed as edge filters, that is the real scope risk of m3.
2. **`_RESUME_ACTIVE_STATES` and resume.** `resume_plan` (`workflow.py:339-368`) maps phase→`current_state` via the hardcoded
   planning-phase dict `_RESUME_ACTIVE_STATES` (`workflow.py:326-336`) and spawns `python -m megaplan <phase>` subprocesses
   (`workflow.py:315-323`). p1 #2 flags this as a second subprocess driver. m3 keeps resume working (Done criterion 6) but
   must decide whether to leave `_RESUME_ACTIVE_STATES` as-is (planning still owns these phase names) or slot-parameterize it.
   Default: leave it — resume's subprocess port is the deferred auto.py concern, out of m3 scope; only ensure the relocated
   pack does not break the phase→state names it reads.
3. **Thin stage wrappers (`stages/{plan,gate,prep,critique,revise,finalize,execute,review,tiebreaker}.py`) — relocate or keep
   shared?** They delegate to `InProcessHandlerStep`. Since the (1)+(2) collapse changes how `next` is produced, decide
   whether the per-phase Step shells + the builders `build_inprocess_planning_steps`/`build_revise_step`/`build_review_step`
   (`inprocess_step.py:232-282`) move into the pack or stay in `_pipeline/stages/`.
4. **Import side-effects on relocation.** `_pipeline/planning.py` is imported lazily by `_planning_builder`
   (`registry.py:416`). If `prompt_key` ever graduates (option a), the pack inherits the creative/doc load-order constraint
   (`creative/__init__.py:35` imports `prompts` for `register_pipeline_prompt` side-effects). Confirm the kept-as-annotation
   default avoids this.

## Constraints

- **Does NOT need the deferred auto.py in-process port.** The v1 draft asserted "the collapse is only safe once auto.py runs
  in-process on the unified executor" (`deferred/m4-planning-packification.md:88-89`); v2 **rejects** that coupling. m3 needs
  only m1's *executor merge* (one override-complete `run_pipeline*` path) — encodings (1)+(2) are collapsed on the in-process
  executor that already exists; encoding (3) is reconciled in `workflow.py` independently of any driver. The two subprocess
  drivers (`resume_plan`, MegaLoop `loop/engine.py`) stay intact (EPIC deferred list; p1 #2). **Call this out explicitly in
  the plan: no auto port is performed or assumed.**
- **Discovery-integrity guard (m1) must be in place** before dropping `_BUILTIN_NAMES`, else a planning that fails to import
  becomes a silent absence (`registry.py:118-121`).
- **Back-compat / cloud:** keep the `megaplan status` JSON contract m1 pinned green (cloud supervisor reads `next_step`); do
  not break any `from megaplan…` import the supervisor SSHes into; keep planning phase names valid in existing profiles.
- **No new pipeline branches / topology change** — same `prep→plan→critique→gate→…→review` shape (`planning.py:33-39`).

## Done criteria (testable)

1. `megaplan/_pipeline/planning.py` no longer exists (or is a thin re-export shim, decided at plan time); the compile logic
   lives at `megaplan/pipelines/planning/__init__.py::build_pipeline` (zero-arg).
2. `_BUILTIN_NAMES` is empty/removed; `register_pipeline("planning", …)` is gone; a test asserts `registered_pipelines()`
   still returns `"planning"` **via discovery**, and a discovery-integrity test asserts planning compiles + is discoverable
   (m1 guard exercised for planning).
3. `_label_for` and `_gate_next_step` are deleted from `inprocess_step.py`; `grep` across `megaplan/` + `tests/` finds no
   callers; a test asserts the in-process walk's next-step comes only from graph edges.
4. **`workflow_next` reconciliation is implemented and tested:** a test constructs a state at each planning state across at
   least `full` and `light` robustness and asserts `workflow_next(state)` ⟷ the pack graph's outbound edges agree (modulo the
   documented robustness/predicate/`"step"` projection); and an end-to-end test asserts `status.next_step`, an override
   `valid_next`, and doctor's `recoverable` for the same state are mutually consistent (no desync — the p1 #4 failure mode).
5. **Parity gate green:** m1's `test_pipeline_parity.py` (decision-field diff + reprompt/downgrade/tiebreaker branch coverage)
   passes unchanged — direct `handle_*` vs the relocated discovered pipeline produce byte-identical artifacts + identical
   state transitions.
6. **Resume of a plan created as the old built-in still works via an alias.** A plan whose `state.json` was created under the
   old `"planning"` built-in resumes without `KeyError` — an old→new pipeline-name alias (EPIC cross-cutting,
   `EPIC.md:127`) makes `get_pipeline`/resume resolve. Test: load a fixture state stamped with the legacy registration and
   resume it green.
7. The `prompt_key` decision is implemented + tested: kept-as-annotation → a test asserts receipts (`receipt.py:94`) and the
   `prompt_key_overlay` (`pattern_topology.py:249`) still carry the key while dispatch ignores it.
8. The five tests importing `build_inprocess_planning_steps`/`build_revise_step`/`build_review_step`
   (`test_pipeline_parity.py:32`, `test_pipeline_resume.py:26`, `test_pipeline_planning_e2e.py:27`,
   `characterization/test_pipeline_golden.py:37`) and `test_pipeline_typed_edges.py:148` pass (updated for the collapsed
   routing). Full suite + `test_import_surface.py` stays green; no new import cycles.

## Touchpoints

- **Registry / relocation:** `megaplan/_pipeline/registry.py` (53, 154-155, 382-389, 415-424); new
  `megaplan/pipelines/planning/__init__.py` + `SKILL.md` (+ `prompts/` only if graduated); delete/shim
  `megaplan/_pipeline/planning.py`.
- **Routing collapse (1+2):** `megaplan/_pipeline/stages/inprocess_step.py` (78, 141-200, 232-282); thin shells
  `stages/{plan,gate,prep,critique,revise,finalize,execute,review,tiebreaker}.py`.
- **`workflow_next` reconciliation (3):** `megaplan/_core/workflow.py` (49-54, 184-242, 282-302, 326-336) and its consumers:
  `cli/status_view.py:748`, `cli/__init__.py:305`, `handlers/override.py` (155, 263, 269, 361, 385, 438, 542, 604, 671, 800,
  855, 862, 884), `handlers/shared.py` (437, 476, 531, 571), `handlers/gate.py` (154-161), `handlers/init.py:472`,
  `handlers/tiebreaker.py` (57, 136 — `workflow_transition`), `execute/step_edit.py` (117, 195, 224, 257),
  `observability/introspect.py:375`, `observability/doctor.py:426`. Public re-exports: `megaplan/__init__.py:43,67`,
  `_core/__init__.py`.
- **Edge dispatch (read-only, must keep working):** `megaplan/_pipeline/executor.py` (262-300, and the merged single path
  from m1).
- **`prompt_key` readers:** `_pipeline/receipt.py:94`, `_pipeline/pattern_topology.py:249`, `_pipeline/prompts.py`.
- **Template references (do not modify):** `megaplan/pipelines/creative/`, `megaplan/pipelines/doc/`.
- **Resume / cloud contract (verify, do not port):** `_core/workflow.py::resume_plan`; `megaplan status` JSON; the four
  `megaplan.chain` names the cloud supervisor imports (m1-pinned).

## Anti-scope

- **No realization backends** (EvidenceRealizer/CodeRealizer, PR #43) — that is m4 / deferred (`EPIC.md:89-102, 116`).
- **No config-object change** — no `HandlerContext`/`services` bag, no `args_to_hctx`; handlers keep the
  `argparse.Namespace` contract (`inprocess_step.py:50-72`). That is m4.
- **No auto.py in-process port** — m3 performs and assumes no in-process driving; the two subprocess drivers (`resume_plan`,
  MegaLoop) stay as-is; the cloud↔`_phase_command` coupling is untouched here.
- **No planning prompt-content rewrite** — relocating prompt modules ≠ editing their text.
- **No new pipeline branches / topology change** — same prep→plan→critique→gate→…→review shape.
