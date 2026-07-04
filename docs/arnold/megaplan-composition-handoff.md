# Megaplan Composition Handoff — M1 Launch-Gate Doctrine

**Milestone:** M1 — Megaplan Compositional Migration
**Status:** Launch-gate handoff (pre-implementation doctrine)
**Date:** 2026-07-03

---

## 1. Purpose

This document is the **M1 composition handoff**. It records the authoritative
doctrine for the Megaplan compositional migration, the temporary-path ledger
(at launch: none), and the runtime gaps deferred to later milestones. It is
not a completion claim — it is a gate artifact that constrains implementation
before the first workflow edit lands.

The handoff must be acknowledged before Phase 1 (neutral subworkflow
compilation) or Phase 2 (Megaplan workflow edits) proceeds.

---

## 2. Source Authority Doctrine

### 2.1 Compositional Python Source Is Authoritative

The canonical Megaplan workflow is expressed as **compositional Python source**
using `@workflow` / `@pipeline` and `@step` / `@phase` decorators. This source
**owns** Megaplan product semantics:

- Loops are loops.
- Gates are branches.
- Tiebreaker is a subworkflow.
- Review rework is an explicit cycle.
- Human intervention is a suspension point.
- Task execution fanout is not hidden behind one opaque handler.
- Timeout, retry, model routing, escalation, override, and resume behavior are
  declared as workflow structure or policy rather than implicit handler effects.

The canonical source path is `arnold_pipelines/megaplan/workflows/workflow.py`
(see `docs/arnold/megaplan-source-path-reconciliation.md` for the full live
path inventory).

**Source-authority rule:** If a reviewer cannot see the real Megaplan control
flow in the canonical compositional source, the milestone is not complete.
Handler bodies, compatibility modules, and `native_program` shells do not
substitute for visible source structure.

### 2.2 Compiled Manifests and Runtime Outputs Are Derived Artifacts

`WorkflowManifest` is the stable normalized runtime, replay, inspection, and
interchange contract. It proves compiled behavior and durable execution, but it
is **not** a second source of product semantic truth separate from canonical
source.

- Manifests are compiled output — never hand-authored source of truth for
  Megaplan composition.
- Traces are structural evidence — they record execution but do not author
  topology.
- Golden artifacts (scenario traces, behavior fixtures) prove parity but do not
  define product semantics.

**Derived-artifact rule:** Any implementation that treats a compiled manifest,
projected `Pipeline`, or runtime trace as the source-authoritative
representation of Megaplan product semantics is non-conformant even if it can
execute.

### 2.3 `Pipeline.native_program` Is Compatibility Dispatch Substrate

`Pipeline.native_program` is a **compatibility dispatch substrate** for runtime
execution and projection. It carries the compiled `NativeProgram` from
canonical source through the neutral native compiler.

- It is **not** the source-authoritative representation of product semantics.
- It is useful proof that execution can move away from graph-era bundles.
- It never proves report conformance by itself.
- Non-null `native_program` is substrate evidence, not semantic completeness.
- Resume/replay must never infer a new topology from `Pipeline.native_program`
  alone when source and compiled metadata disagree; source-owned semantics win.

**Compatibility-substrate rule:** Any milestone closure based only on non-null
`native_program`, projected shells, route labels, or native traces is a false
pass.

---

## 3. Doctrine Precedence

When documents appear to conflict, use this precedence order:

1. **Canonical Megaplan product semantics** are owned by visible compositional
   native Python source (`arnold_pipelines/megaplan/workflows/workflow.py`),
   declared workflow policy, or an audited pure phase body.

2. **`WorkflowManifest`** is the stable normalized runtime, replay, inspection,
   and interchange contract. It proves compiled behavior and durable execution,
   but it is not the final Megaplan authoring doctrine and must not become a
   second source of product semantic truth separate from canonical source.

3. **`Pipeline.native_program`** and projected compatibility shells are
   migration substrate and dispatch compatibility. They are useful proof that
   execution can move away from graph-era bundles, but they never prove report
   conformance by themselves.

This precedence is drawn from `docs/arnold/megaplan-native-representation-alignment-plan.md`
(§Doctrine Precedence) and `docs/arnold/native-composition-contract.md` (§Doctrine).

---

## 4. Temporary-Path Ledger

### 4.1 Status at M1 Launch: **None**

At M1 launch, no product-specific compiler, runtime, or projection
paths exist. The neutral native substrate (`arnold/pipeline/native/compiler.py`,
`arnold/pipeline/native/runtime.py`, `arnold/pipeline/native/graph_projection.py`)
contains no Megaplan vocabulary or product-specific branching. All subworkflow
lowering, execution, and projection paths are neutral.

### 4.2 Temporary-Path Classification Rules

If implementation later adds product-specific behavior, each path must be
recorded here with:

| Field | Description |
|-------|-------------|
| **Path** | File and line reference |
| **Classification** | `TEMPORARY_MEGAPLAN_ONLY` |
| **Blocking status** | `BLOCKING` — report conformance blocked until resolved |
| **Removal owner** | M2 or M3 milestone label |
| **Generalization target** | Neutral native fixture that replaces the temporary path |

### 4.3 Current Ledger

| # | Path | Classification | Blocking | Removal Owner | Notes |
|---|------|---------------|----------|---------------|-------|
| — | *(none)* | — | — | — | No temporary paths at M1 launch. |

**Ledger rule:** Any report row depending on a `TEMPORARY_MEGAPLAN_ONLY` path
remains non-conformant until M3 proves the behavior through neutral native
fixtures and removes or reclassifies the temporary path.

---

## 5. Runtime Follow-Ups (Deferred to M2/M3)

The following runtime gaps are documented here as **M2/M3 follow-ups**. They are
not M1 completion claims. They must be resolved before the composition epic can
claim report conformance for the affected traceability rows.

### 5.1 Shallow Child State Copy

**Status:** Deferred to M2/M3.

The current runtime uses shallow-copy isolation for subworkflow state. When a
parent workflow invokes a child subworkflow, the child receives a shallow copy
of the relevant state slice. Deep-copy semantics or explicit input-mapping-by-
contract are not yet implemented.

- **Impact:** Nested subworkflows that mutate shared mutable objects may
  pollute parent state. This is a correctness risk for Megaplan loops where
  critique→gate→revise iterations carry accumulated state.
- **Required for:** Traceability rows D2 (Critique), D4 (Gate/Revise), D5
  (Tiebreaker), D10 (Review Caps).
- **Owner:** Composition M2 (subworkflow execution contract) or M3 (runtime
  hardening).
- **Proof gate:** A fixture that demonstrates parent state is not mutated by
  child subworkflow side effects when input mapping does not declare that
  mutation as an output.

### 5.2 Composite Cursor Resume

**Status:** Deferred to M2/M3.

The runtime can **write** composite cursors (via `save_composite_resume_cursor`,
dual-write to `state.json::resume_cursor` and `composite_resume_cursor.json`),
but it cannot yet **resume** from them. The resume path in `run_native_pipeline`
only handles single-level cursor restoration. Parent+child restoration from a
composite cursor is not implemented.

- **Impact:** If Megaplan suspends mid-critique-loop (a subworkflow inside the
  top-level workflow), it cannot resume from a composite cursor. This directly
  impacts the human-gated suspend/continue path required by the milestone.
  Human suspension points inside subworkflows are not fully resumable.
- **Required for:** Traceability rows D1 (Prep/Plan), D11 (Human/Control), D12
  (Runtime/Trace).
- **Owner:** Composition M2 (path-addressed checkpoints) or M3 (runtime
  hardening).
- **Proof gate:** A process-death resume test starting from a composite cursor
  inside a subworkflow, restoring parent+child state and continuing execution.

### 5.3 Iteration IDs Not Embedded in Public Stage Names

**Status:** Deferred to M2/M3.

Loop iteration coordinates are tracked internally by the runtime, but iteration
IDs are not yet embedded in public stage names, trace records, or checkpoint
paths with stable, non-ambiguous semantics.

- **Impact:** Repeated loop iterations (e.g., critique→gate→revise cycle
  iterations) may lack distinct public identities. Resuming a specific iteration
  or referencing iteration-scoped artifacts depends on internal iteration
  counters that are not surfaced in the public stage name contract.
- **Required for:** Traceability rows D4 (Gate/Revise), D10 (Review Caps),
  D12 (Runtime/Trace).
- **Owner:** Composition M2 (path identity and loop semantics) or M3 (trace
  hardening).
- **Proof gate:** A loop iteration trace snapshot that shows distinct,
  monotonic iteration coordinates in public stage paths, and a resume test that
  targets a specific iteration by its public path identity.

### 5.4 Public Stage-Name Suffixing for Inlined Subworkflows

**Status:** Deferred to M2.

M1 keeps Megaplan's public stage IDs (`prep`, `plan`, `critique`, `gate`,
`revise`, `tiebreaker_run`, `tiebreaker_decide`, `finalize`, `execute`,
`review`, `halt`, `override`) stable while making subworkflow boundaries
source-visible. The V1 source compiler does not yet provide a neutral rule for
inlining named local subworkflows without changing repeated public stage names
or appending product-specific suffixes.

- **Impact:** The canonical source can name the composition boundaries, but the
  decorated top-level route spine must remain the compiled public-stage
  authority until neutral suffix/path rules exist.
- **Required for:** Traceability rows D4 (Gate/Revise), D5 (Tiebreaker), D10
  (Review Caps), D11 (Human/Control), D12 (Runtime/Trace).
- **Owner:** Composition M2 (public stage path identity).
- **Proof gate:** A neutral compiler fixture that inlines repeated named
  subworkflows, produces stable public child path coordinates without
  Megaplan-only suffixing, and preserves the existing Megaplan route labels.

---

## 6. Relationship to Other Artifacts

| Artifact | Relationship |
|----------|-------------|
| `docs/arnold/native-composition-contract.md` | M0 bridge contract — this handoff inherits its doctrine and extends it for M1. |
| `docs/arnold/megaplan-native-representation-alignment-plan.md` | Traceability matrix and epic responsibilities — this handoff defers runtime gaps to the owning milestones named there. |
| `docs/arnold/megaplan-source-path-reconciliation.md` | M1 launch-gate source-path authority — this handoff references its live path inventory. |
| `docs/arnold/megaplan-semantics-carrier-table.md` | (T3) Handler purity classification — this handoff's source-authority doctrine is what the carrier table enforces. |
| `docs/arnold/megaplan-artifact-manifest.md` | (T4) Golden artifact manifest — derived artifacts doctrine recorded here. |
| `.megaplan/plans/m1-megaplan-compositional-20260703-0954/plan_v1.meta.json` | Parent plan — this handoff satisfies the T2 launch gate. |

---

## 7. Doctrine Gate Marker

**M1 doctrine gate label:** COMPOSITION-HANDOFF AUTHORITY.

This document is the pre-implementation composition doctrine required by the
M1 launch gate. No Megaplan workflow edit shall land before the following are
acknowledged:

1. Compositional Python source is authoritative for Megaplan product semantics.
2. Compiled manifests and runtime outputs are derived artifacts.
3. `Pipeline.native_program` is compatibility dispatch substrate, never final
   authoring truth.
4. No temporary Megaplan-only paths exist at launch. Any added later must be
   ledgered with `TEMPORARY_MEGAPLAN_ONLY`, file reference, `BLOCKING`, and
   M2/M3 removal owner.
5. Shallow child state copy, composite cursor resume, and iteration ID
   surfacing are deferred to M2/M3 — not claimed as M1 completions.
6. Public stage-name suffixing for inlined named subworkflows is deferred to M2
   and cannot be claimed as an M1 neutral compiler feature.

---

## 8. Summary

| Item | Status |
|------|--------|
| Source-authority doctrine recorded | ✓ |
| Derived-artifact doctrine recorded | ✓ |
| `native_program` compatibility-substrate doctrine recorded | ✓ |
| Temporary-path ledger | Empty (none at launch) |
| Shallow child state copy | Deferred to M2/M3 |
| Composite cursor resume | Deferred to M2/M3 |
| Iteration IDs in public stage names | Deferred to M2/M3 |
| Public stage-name suffixing for inlined subworkflows | Deferred to M2 |

**Ready for Phase 1 implementation.** All doctrine constraints are recorded.
No temporary paths exist. Runtime gaps are deferred with named owners and
blocking proof gates.
