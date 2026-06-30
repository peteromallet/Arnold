# M0a: Core ContractResult Type

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Freeze the single seam primitive that every other milestone and both planes (Step-IO data plane + Evidence-First control plane) import: ONE `ContractResult` dataclass. It carries a typed payload, a `schema_version`, a `status` discriminant `{completed | suspended | failed}`, a typed `Suspension` shape, and the generic provenance/evidence fields `evidence_refs`, `authority_level`, `provenance`, `freshness`.

This is the shared contract BOUNDARY, not an implementation. It is a frozen TYPE only — no validation, no enforcement, no behavior. It is consolidated into a single primitive rather than a 4th carrier added alongside the two existing envelopes (`RunEnvelope`, `RuntimeEnvelope`) and the dormant typed Ports. Defining it once, above both planes, is what kills the define-twice-then-reconcile rework: the data-plane/model-seam work and Evidence-First enforcement both `import` this type rather than each defining their own.

This milestone should change no runtime behavior. It introduces a type and its serialization, nothing more.

## Scope

IN:

- Define ONE `ContractResult` dataclass on the neutral platform surface (`arnold/pipeline/types.py`) so it is `from arnold.pipeline import ...`, a platform primitive and not a megaplan opinion.
- Fields: typed `payload`, `schema_version` (a schema HASH, not an iteration counter), `status` enum `{completed | suspended | failed}`, `provenance`, `freshness`, `evidence_refs`, `authority_level`. Evidence and authority are FIRST-CLASS fields, not optional slots bolted on later.
- `ArtifactRef` is a FIRST-CLASS type/field (B3). The `payload` MAY be a typed MANIFEST that references artifacts via `ArtifactRef`, not only inline JSON — media/large-data can't be the payload itself. The manifest still keeps `ContractResult` itself small (refs, not inlined blobs); content-level validation of the referenced blob lives in m0b.
- Define the typed `Suspension` shape as a typed INTERACTION ENVELOPE (B4) carried when `status == suspended`: `kind`/`awaitable` (human OR render-job/quota/upload), `prompt`, `display_refs[]`, `resume_input_schema` (open + structured), `resume_cursor`, `thread_ref`, `actor`, and `deadline`/`on_timeout`/`default_action`. Suspension is the LOOP DRIVER, not merely an interruption. BAKE these FIELDS now — they sit inside the frozen m0a type, so adding them later is a contract migration — but IMPLEMENT only the existing human/manual wait behavior; the richer awaitables are designed-in but not built here.
- Make the field set generic enough to stay a platform primitive across 50–100 pipelines: no megaplan-phase-specific assumptions leak into it (no `gate`/`critique`/`review` fields baked in).
- Stable (de)serialization to/from the megaplan artifact layer, with `schema_version` always present on the wire.
- A canonical module-level doc explaining the primitive, its fields, the `status` discriminant, and the import contract for downstream milestones and Evidence-First.

OUT:

- No validator function (that is m0b).
- No schema registry / version-retention machinery (m0b).
- No chokepoint, no read-lenient/write-strict gating, no shadow/warn/enforce (m1).
- No wiring into any stage, executor, handler, or worker.
- No enforcement of any kind anywhere.
- No suspension-aware composition logic (m4) — this milestone only defines the `status`/`Suspension` SHAPE, not how it propagates.

## Locked Decisions

- ONE `ContractResult` primitive. No 4th envelope is introduced; the primitive consolidates the dormant typed-ports vocabulary (data seam) and the model-IO envelope into a single shape.
- ContractResult stays SMALL: NO 4th status beyond `{completed | suspended | failed}`. VALIDATED by the N=1 overfit check — a 5-pipeline panel (design-studio human-loop / multimodal+vision-gate / live-monitor-streaming / research-swarm / deterministic-ETL) independently converged that ContractResult must stay small and generalization is pushed into ADJACENT primitives, not a richer status enum.
- `ArtifactRef` is a first-class type/field and `payload` may be a typed MANIFEST referencing artifacts (B3) — but the manifest carries refs, not inlined blobs, so the type stays small.
- The `Suspension` shape is a typed INTERACTION ENVELOPE (B4) whose FIELDS are baked now (frozen-type → later add = migration); only existing human/manual wait behavior is implemented.
- The contract SHAPE is shared across seams; per-seam MACHINERY lives behind it in later milestones. One contract at the boundary, not two seam dialects.
- The `status` discriminant `{completed | suspended | failed}` is hoisted into the TYPE here, before any enforcement, because the edge hunt falsified the "human-seam/composition falls out free" claim — `StepResult` had no suspended/pending state and human-wait was an ad-hoc `next="halt"` + `state_patch={"_pipeline_paused": True}` side-channel (`_pipeline/executor.py:262`).
- `schema_version` is a schema HASH, not a monotonic counter.
- Evidence and authority are first-class fields, defined once above BOTH planes; Evidence-First imports THIS type (its old "define EvidenceRef" milestone is absorbed here) and imports m0a ONLY — not the validator, registry, or anything downstream.
- Insertion point is the neutral platform surface `arnold/pipeline/types.py` (where typed `Port`/`PortRef` already live at line 234), not `megaplan/`.
- 2nd-PIPELINE CO-DESIGN CONSTRAINT (pre-mortem risk 1, the biggest — N=1 overfit): the type is designed against a structurally-different 2nd pipeline — the deterministic Arnold-native `evidence-pack` verifier (model-LESS tool steps, data by-reference, fan-out-reduce, typed verdict, NO planning shape) — as a CO-DESIGN constraint FROM THE START, not just an m8 acceptance test (m8 VALIDATES the shape, it does not meet it first). The `ArtifactRef` / typed-manifest payload and the `status` / `Suspension` shape must demonstrably express the evidence-pack pipeline's needs (external by-ref data, multi-content-type, typed non-megaplan verdict, human suspend/resume) as cleanly as they express megaplan's — so the frozen primitive is a platform shape, not a megaplan-anatomy fit.

## Open Questions

- Exact field types/encoding for `provenance` and `freshness` (structured sub-dataclass vs. typed mapping).
- Whether `payload` is a generic over a per-pipeline content type, a typed mapping, or a tagged union, given the platform-scale schema-divergence constraint.
- How `schema_version` (the hash) is computed and from what canonical schema representation.
- Relationship/coexistence of `ContractResult` with the existing `RunEnvelope`/`RuntimeEnvelope` carriers (composition vs. adjacency) — type-level only here.

## Constraints

- No behavior change anywhere; this is a type-and-serialization-only milestone.
- The primitive must be importable by both planes without importing any megaplan-specific module (no layering inversion).
- Serialization must round-trip and always emit `schema_version`.
- The type must be generic enough not to become a god-type as pipelines proliferate.
- Must base cleanly on `arnold-epic` (inherits Port vocabulary at `arnold/pipeline/types.py:234` + the `StepResult`/`AdvanceOutcome` driver seam).

## Done Criteria

1. `ContractResult` exists as ONE dataclass on `arnold/pipeline/types.py` with all required fields (`payload`, `schema_version`, `status`, `provenance`, `freshness`, `evidence_refs`, `authority_level`) and is covered by type/serialization tests.
2. The `status` enum `{completed | suspended | failed}` exists and is part of the frozen type.
3. The typed `Suspension` interaction-envelope shape exists with all baked fields (`kind`/`awaitable`, `prompt`, `display_refs[]`, `resume_input_schema`, `resume_cursor`, `thread_ref`, `actor`, `deadline`/`on_timeout`/`default_action`) and is carried by the type when `status == suspended`; only the existing human/manual wait behavior is implemented, with the richer awaitable fields present-but-unimplemented.
4. `ArtifactRef` exists as a first-class type/field and `payload` supports being a typed manifest that references artifacts (not only inline JSON), while `ContractResult` itself stays small (refs, not inlined blobs).
5. `schema_version` is present on every serialized `ContractResult` and is a schema hash.
6. Both planes can `import` the primitive from `arnold.pipeline` without a megaplan dependency; a test demonstrates the Evidence-First-style import path.
7. No validator, registry, chokepoint, or enforcement is introduced; tests confirm runtime behavior is unchanged.
8. A canonical module-level doc describes the primitive and the import contract for downstream milestones.
9. The frozen type demonstrably expresses the structurally-different `evidence-pack` verifier shape (model-less by-ref data via `ArtifactRef`/typed manifest, multi-content-type, typed non-megaplan verdict, human suspend/resume via the `Suspension` envelope) as cleanly as megaplan's — co-designed against it from the start, NOT retrofitted at m8; an artifact/test shows the evidence-pack shape is expressible without contorting or extending the type.

## Touchpoints

- `arnold/pipeline/types.py` (where `Port`/`PortRef` live at line 234; new `ContractResult`, `status` enum, `Suspension` interaction envelope, first-class `ArtifactRef`)
- `arnold/pipeline/__init__.py` (export surface)
- megaplan artifact (de)serialization layer
- shared schema/types module docs
- type + serialization tests; an Evidence-First import-path test

## Rubric

- Profile: `apex`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is the type every later milestone and both planes inherit. A wrong abstraction here is the single most expensive rework in the epic — it would force every seam and Evidence-First to re-adopt a corrected shape. Freezing the right generic primitive (with `status`, `Suspension`, evidence, and authority first-class) early is the load-bearing decision, so it earns the top tier despite being behavior-free.
