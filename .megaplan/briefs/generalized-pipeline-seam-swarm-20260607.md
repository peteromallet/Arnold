# Generalized Pipeline Seam Swarm

Date: 2026-06-07

This note records the DeepSeek swarm used to review the proposed generalized pipeline direction for Megaplan/Arnold, and folds the findings into a project-shaping recommendation.

## Swarm Questions

Nine independent DeepSeek workers reviewed different parts of the proposal against the current repository:

1. **Clean separation**: Is the split between `arnold.pipeline`, Megaplan-specific planning policy, and chain/epic orchestration clean? What leaks?
2. **Maximal elegance**: Is the proposed architecture too large? What should be deleted, delayed, or collapsed?
3. **Current code contradictions**: Where does the current code contradict the proposed boundaries? Which contradictions must be fixed before extraction?
4. **Step contract boundary**: What belongs in `StepContract`, what does not, and what is the safest first slice?
5. **Runner boundary**: Where should `run_step` / `run_pipeline` start and end? What should remain outside them?
6. **State/evidence runtime**: Which runtime pieces can move to a neutral package, and which must stay Megaplan-specific?
7. **Chain vs pipeline**: Is the Step -> Pipeline -> Chain/Epic layering right? What chain code should generalize first?
8. **Migration risk**: What could break the active Evidence-First epic or collide with the earlier Pipeline Unification work?
9. **Non-Megaplan proof**: What existing pipeline best proves the abstraction is not fake?

All nine workers completed successfully.

## Overall Verdict

The proposed direction is sound, but the first implementation should be narrower than the earlier project-scope document implied.

The clean core is already present:

- `arnold.pipeline` has mostly neutral graph, step, port, contract, and executor primitives.
- Megaplan already consumes those primitives while still carrying planning-specific phase policy in `arnold.pipelines.megaplan`.
- The existing `arnold/pipelines/evidence_pack` package is already a useful non-Megaplan proof candidate.

The main correction: do not build a parallel new runner stack. The existing `arnold.pipeline.executor.run_pipeline` should remain the canonical walker. If we add convenience APIs, they should be thin wrappers over that executor, not another implementation of the walk.

## Strongest Boundary

The most elegant layer model is:

```text
arnold.pipeline
  Generic step, port, contract, graph, executor, and neutral outcome primitives.

arnold.pipelines.<package>
  Domain package that defines concrete steps, schemas, bindings, policies, and artifacts.

arnold.supervisor / neutral control layer
  Cross-run orchestration primitives: RunOutcome, ControlTarget, run nodes, ladders, dependency assertions.

arnold.pipelines.megaplan.chain / supervisor binding
  Megaplan epic lifecycle: milestone YAML, Git/PR policy, merge gates, profiles, planning states, Evidence-First semantics.
```

Megaplan should become one pipeline package built on the generic substrate, not the owner of the substrate.

## What To Fix First

The most concrete leaks are small and should be fixed before a large extraction:

1. `arnold/pipeline/schema_registry.py` hardcodes `.megaplan/plans` and `MEGAPLAN_CONTRACT_SCHEMA_ROOT`.
2. `arnold/pipeline/step_io_policy.py` searches for `.megaplan` path sentinels.
3. `arnold/pipeline/artifacts.py` still has a lazy compatibility import from Megaplan, already marked for deletion in M7.
4. There are competing `StateDelta` / `apply_delta` concepts in `arnold.pipeline.state` and `arnold.pipelines.megaplan._pipeline.types`.
5. `arnold/pipelines/megaplan/_pipeline/executor.py` claims stronger isolation than it actually has; the docstring should be corrected until the imports are gone.

The smallest high-leverage correction is to parameterize path policy in the generic layer. Let Megaplan supply `.megaplan/plans` as configuration rather than letting neutral modules know that convention.

## Step Contract Scope

The swarm converged on a thin `StepContract`, not a broad step object.

Minimal useful fields:

- `name`
- `schema_key`
- `capture_schema_key`, defaulting to `schema_key`
- `output_kind`
- `normalizer`
- `compatibility_mode`

Keep out:

- worker/model routing
- profile/depth/robustness policy
- output filename templates
- state transitions
- prompt references
- model token budgets
- Megaplan gate vocabulary

First slice: add a read-only Megaplan `step_contracts.py` registry that mirrors existing dicts in `model_seam.py`, `workers/_impl.py`, and schema mappings. Add characterization tests proving the derived views match current behavior, then flip consumers in a later slice.

## Runner Scope

Do not create a second walker.

A safe runner API can exist, but only as a thin wrapper that:

- resolves plan / pipeline identity
- materializes a `StepContext`
- validates that the requested step is reachable
- calls the canonical executor
- returns a structured outcome

It must not own retries, stall detection, subprocess supervision, cost caps, human gates, lifecycle event policy, or independent state writes. Those remain in `drive()`, supervisor policy, or the caller.

## Runtime Extraction

`arnold.pipeline._runtime` is a reasonable eventual seam, but should be extracted only where there is a real second consumer.

Move candidates, in order:

1. `BlobStore` protocol and implementations.
2. `StoredEvent` plus a neutral event projector interface.
3. Atomic I/O and journal helpers, after schema-aware helpers are parameterized.
4. A generic `StateCache[V]` protocol, with Megaplan state as one implementation.
5. Content-addressed record patterns, while keeping Megaplan capsule/warrant schemas in Megaplan.

Do not move the Megaplan `Store` protocol, `PlanRepository`, `MultiStore`, concrete store mixins, or `_core/state.py`. Those are domain-level Megaplan machinery.

## Chain And Supervisor

The Step -> Pipeline -> Chain/Epic layering is right, but the neutral control vocabulary currently lives too low inside Megaplan.

Good future extraction candidates:

- `RunOutcome`
- `ControlTarget`
- `ControlProjection`
- `RunStateView`
- neutral supervisor node/dependency/ladder data structures

Keep in Megaplan:

- Git/PR mechanics
- milestone YAML fields specific to planning
- profile/vendor/depth/critic knobs
- planning state-machine bindings
- Evidence-First authority/provenance policy
- bakeoff rubric/profile-matrix details
- CI and rollout gates

## Migration Warning

The active Evidence-First epic should still go first, but not necessarily all the way to M11 before generalization work starts.

Recommended sequencing:

1. Complete Evidence-First M0-M3 first.
2. Use those milestones to settle engine/target isolation, the evidence contract, authority readers, and a first execute -> review -> done proof.
3. Then start generalized pipeline work on the shared branch, with characterization tests protecting the Evidence-First semantics.
4. Co-design later Evidence-First routing/capability milestones with the generalized control/supervisor layer, rather than building both independently.

No-go changes while Evidence-First M0-M3 are active:

- Do not flip event/WAL authority out from under `is_task_satisfied`.
- Do not delete the subprocess seam before engine/target isolation and first-slice proof are green.
- Do not relocate planning package discovery or route validation before the transition-authority story is settled.
- Do not merge a second Arnold umbrella namespace without checking the forward-port ledger against `arnold-epic`.

## Non-Megaplan Proof

The best proof pipeline is the existing `arnold/pipelines/evidence_pack` verifier.

It already imports from `arnold.pipeline`, not Megaplan. It exercises:

- graph construction
- parallel fan-out and join
- typed ports and cardinality
- contract result serialization
- suspension/resumption
- read/write refs
- deterministic reduce behavior
- artifact-backed attestation

Success criteria for the abstraction:

- zero Megaplan imports in `arnold/pipelines/evidence_pack`
- deterministic end-to-end run through initial and continuation pipelines
- typed port mismatch caught at construction or execution boundary
- no Megaplan vocabulary leak such as `STATE_*`, `GateRecommendation`, `.megaplan/plans`, `plan_vN.md`, or `gate.json`
- at least one second non-Megaplan demo reuses the same parallel/reduce primitives

## Revised Project Shape

The generalized pipeline project should be scoped as:

1. Characterize current neutral/generic boundaries and add static leak tests.
2. Remove `.megaplan` path assumptions from `arnold.pipeline`.
3. Add a read-only Megaplan `StepContract` mirror and characterization tests.
4. Flip schema/normalizer/compatibility consumers to derive from the contract registry.
5. Add a thin ergonomic runner wrapper over the existing executor.
6. Promote neutral run/control vocabulary out of Megaplan when Evidence-First M0-M3 are green.
7. Use `evidence_pack` as the non-Megaplan proof pipeline.
8. Extract runtime utilities only after the second consumer proves the need.

This is smaller and cleaner than "abstract everything Megaplan does." The right goal is: generic pipeline primitives first, Megaplan as a domain package second, chain/epic policy above both.
