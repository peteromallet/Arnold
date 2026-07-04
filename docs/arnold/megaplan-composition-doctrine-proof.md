# Megaplan Composition Doctrine Proof

**Milestone:** M1 — Megaplan Compositional Workflow Migration
**Status:** Phase 1 launch-gate doctrine — defines source authority and false-pass language
**Date:** 2026-07-02

---

## 1. Purpose

This document is the **composition doctrine proof** for M1. It defines the
authoritative layering that governs all source edits, test conformance claims,
and migration decisions. Every implementation claim, test assertion, and
alignment-plan row must align with this doctrine.

The doctrine is binding, not aspirational. Any implementation that violates a
**must** clause is non-conformant, even if it passes tests.

---

## 2. Source Authority

### 2.1 The Three-Layer Model

The Megaplan composition system has exactly three layers, and their authority
relationship is fixed:

| Layer | Kind | Authority |
|-------|------|-----------|
| **Decorated Python source** | Source-of-truth | **Owns product semantics** |
| **WorkflowManifest** | Compiled output | Derived artifact |
| **Pipeline.native_program** | Dispatch substrate | Runtime shell |

### 2.2 Source-Owns-Semantics Doctrine

**MUST:** Compositional Python source and declared policy own Megaplan product
semantics. Specifically:

- The canonical `build_pipeline()` in `arnold_pipelines/megaplan/workflows/planning.py`
  is the **sole authoritative source** of Megaplan workflow topology, stage
  order, handler assignments, routing decisions, and composition boundaries.
- Declared policy — including stable IDs, decision vocabulary, validator rules,
  input/output schemas, and merge semantics — is **policy that owns semantics**.
  It is authored in source, not derived from runtime observation.
- No semantic claim about Megaplan behavior is valid unless it can be traced
  back to Python source or declared policy in the live
  `arnold_pipelines/megaplan/` package.

**MUST:** Any implementation that derives topology, stage order, routing, or
composition semantics from `WorkflowManifest` or `Pipeline.native_program`
alone — without tracing back to Python source — is non-conformant, even if it
can execute correctly.

**MUST:** Source-compiled artifacts (`WorkflowManifest`, `topology_goldens`,
`native_program`) must be **regenerated** when source changes, not manually
edited to match a desired output. Manual edits to compiled artifacts are
non-conformant.

### 2.3 Live Package Path Authority

**MUST:** The live implementation surface for all Megaplan product code is
`arnold_pipelines/megaplan/` (underscore-separated package name). This is the
plugin root included in the wheel build per `pyproject.toml` line 84.

**MUST:** The stale `arnold/pipelines/megaplan/` dot-path (excluded from wheel
per `pyproject.toml` line 76) carries **no authoritative implementation**.
References to stale dot-paths in docs, plans, or task descriptions are
documentation debt — they must resolve to live underscore equivalents before
any implementation can claim conformance.

**MUST:** No implementation edit may create new files or modules at the stale
`arnold/pipelines/megaplan/` dot-path. Such files would be ghost code excluded
from the built wheel.

---

## 3. Derived Artifact Status

### 3.1 Manifests

`WorkflowManifest` is a **derived artifact**, not a source of truth.

**MUST:** Manifests record the compiled shape of a workflow at a point in time.
They are useful for caching, comparison, and conformance verification, but they
do not author semantics.

**MUST:** If a manifest disagrees with Python source, the **source wins**.
Manifest discrepancies are bugs in compilation or caching, not evidence that
the manifest carries semantic authority.

**MUST:** Hand-authoring a manifest to achieve a desired topology, stage list,
or routing table is non-conformant. The compiler owns manifest generation;
manual manifest edits bypass source authority.

### 3.2 Topology Goldens

Topology goldens are **derived artifacts** used for regression detection.

**MUST:** Topology goldens capture the expected compiled shape at a point in
time. They are test fixtures, not semantic owners.

**MUST:** When a golden disagrees with compiled output from the current source,
the golden is stale — the source is not wrong. The golden must be regenerated
from source, not manually patched.

**MUST:** A test that compares topology goldens without also verifying the
underlying source compilation chain is a false-pass risk. Golden comparison
alone does not prove source authority.

### 3.3 NativeProgram

`Pipeline.native_program` (`NativeProgram`) is a **dispatch substrate** and
compatibility shell, not a source-authoritative representation.

**MUST:** `NativeProgram` exists to enable runtime execution, projection, and
compatibility with existing executor paths. It does not own workflow semantics.

**MUST:** Direct IR construction of `NativeProgram` outside the compiler
(`arnold/pipeline/native/`) is non-conformant. Known direct-construction sites
in `arnold_pipelines/megaplan/_compatibility.py` and
`arnold_pipelines/megaplan/select_tournament/pipeline.py` are M1-M6 migration
targets, not evidence of conformance.

**MUST:** Runtime code that reads `native_program` to determine topology,
stage order, or routing decisions — without also verifying against source —
is fragile and must be treated as bridge debt, not canonical behavior.

---

## 4. False-Pass Prevention Language

### 4.1 Wrapper Graphs

A **wrapper graph** is a compiled artifact that mirrors the shape of a
handler-backed stage list without decomposing the internal structure of
those handlers.

**MUST:** A test that passes because a wrapper graph emits the same
instruction count or label surface as the handler-backed stage list — without
verifying that handler-internal topology is decomposed into visible
compositional structure — is a **false pass**.

**MUST:** False-pass tests must be named and marked explicitly:

```python
@pytest.mark.false_pass_risk(
    reason="wrapper graph passes because handler-backed stages "
           "produce same instruction surface; internal decomposition "
           "not yet verified"
)
```

**MUST:** No alignment-plan row may be marked `implemented` if its only
conformance evidence is a false-pass test against a wrapper graph.

### 4.2 Handler-Owned Routing

Handler-owned routing means routing decisions (decision vocabulary, branch
targets, suspend/resume coordinates, override routes) are implemented inside
handler bodies that are opaque to the composition compiler.

**MUST:** A test that passes because a handler's opaque routing behavior
produces the same observable outcome as declared compositional routing — without
verifying that routing decisions are extracted into visible, compiler-visible
declarations — is a **false pass**.

**MUST:** The following Megaplan handlers currently own routing semantics that
must be decomposed into visible compositional structure in Phase 3:

| Handler | Routing Owned | Decomposition Target |
|---------|--------------|---------------------|
| `handlers/critique.py` | Retry loop, robustness skip, parallel lens dispatch | Visible critique subworkflow with decision branches |
| `handlers/gate.py` | Preflight signal building, reprompt routing, flag/debt branching | Declared gate decision vocabulary |
| `handlers/tiebreaker.py` | Researcher/challenger subworkflow dispatch | Composed researcher + challenger child workflows |
| `handlers/execute.py` | DAG batching, approval gate routing | Declared execute decision + batch iteration |
| `handlers/review.py` | Parallel check dispatch, rework loop | Visible review subworkflow with rework decision |
| `handlers/override.py` | Action route matrix | Declared override decision vocabulary |

**MUST:** Until Phase 3 decomposes these handlers, any test that claims
"routing is compositional" by observing handler output alone is a false pass.

### 4.3 Single-Stage Handler-Backed Passes

**MUST:** A test that passes because a single handler-backed stage (e.g.,
`critique`, `gate`, `tiebreaker`, `execute`, `review`, `override`) produces
the expected output — without verifying that the handler's internal composition
is decomposed into child workflows, decisions, and visible routing — is a
**false pass**.

This applies specifically to tests that claim migration conformance for
handler-backed stages before Phase 3 decomposition.

### 4.4 Implicit State Propagation

**MUST:** A test that passes because ambient Megaplan state flows through
handler bodies without declared input/output contracts at composition
boundaries is a **false pass**.

Compositional workflows require explicit input mapping and output merge
semantics at every child workflow boundary. Implicit state tunneling through
handler-internal module state, global singletons, or ad hoc attribute bags
bypasses source authority.

---

## 5. Conformance Classes

### 5.1 Source-Conformant

A test or implementation claim is **source-conformant** when:

1. Every semantic assertion traces back to Python source or declared policy
   in the live `arnold_pipelines/megaplan/` package.
2. No semantic assertion depends on compiled artifacts (manifests, goldens,
   native_program) as its sole evidence.
3. Handler-internal routing, topology, or composition decisions are either
   decomposed into visible structure or explicitly labeled as pre-migration
   bridge debt.

### 5.2 Bridge-Conformant

A test or implementation claim is **bridge-conformant** when:

1. It passes against the current handler-backed implementation (which is the
   canonical source until Phase 3 migration).
2. It does not claim that handler-backed stages are already decomposed.
3. It is labeled with the bridge-work disclaimer: "Pre-migration scaffolding;
   canonical decomposition gated on M7 + Phase 3."

### 5.3 Non-Conformant

A test or implementation claim is **non-conformant** when:

1. It derives semantics from compiled artifacts without source traceability.
2. It claims migration conformance for handler-backed stages without visible
   decomposition.
3. It creates or depends on stale dot-path implementation.
4. It hand-authors manifests, goldens, or native_program entries.
5. It passes through wrapper-graph false-pass or handler-owned routing
   without explicit false-pass marking.

---

## 6. Phase-Dependent Doctrine

### 6.1 Phase 1 (Current)

- Source-path reconciliation and launch-gate documentation only.
- **No canonical workflow source edits.**
- Tests may verify live path authority and stale path absence.
- All work is bridge-conformant, not source-conformant for migration.

### 6.2 Phase 2

- Neutral native child-workflow compiler/runtime support.
- Additive, generic, non-Megaplan-specific.
- At least one non-Megaplan fixture must use the same path.
- No `@workflow` decorator applied to canonical Megaplan pipeline.

### 6.3 Phase 3 (Blocked — Gated on M7)

- Canonical Megaplan workflow decomposition.
- Handler-backed stages decomposed into visible compositional structure.
- Requires M7 completion manifest or explicit waiver.
- Until unblocked, all Phase 3 claims are bridge debt.

---

## 7. Traceability

### 7.1 Source Authority Trace

For any semantic claim about Megaplan composition:

```
Claim → Python source in arnold_pipelines/megaplan/ → Declared policy
                                                           ↓
                                                  (not manifest, not native_program)
```

If the trace terminates at a manifest, golden, or native_program without
reaching Python source, the claim is non-conformant.

### 7.2 False-Pass Detection Trace

For any test asserting migration conformance:

```
Test pass → Does it verify handler decomposition? → Yes → Source-conformant
                                                  → No  → Is it marked false_pass_risk? → Yes → Bridge-conformant
                                                                                         → No  → NON-CONFORMANT
```

---

## 8. Doctrine Supremacy

**MUST:** This doctrine supersedes any conflicting guidance in individual task
descriptions, plan documents, or alignment-plan rows. If a task description
implies a semantic claim that violates this doctrine, the task is interpreted
as bridge work, not migration completion.

**MUST:** The epic North Star doctrine (compositional Python workflow source
owns product semantics; compiled artifacts are derived) is the root authority.
This document is its M1-specific instantiation.

**MUST:** Any exception to these rules requires an explicit waiver documented
in the launch-gate reconciliation doc and approved in the plan decision
record.

---

## 9. Acceptance

An M1 implementation conforms to this doctrine only if:

1. Every semantic claim is source-traceable to `arnold_pipelines/megaplan/`.
2. No compiled artifact is treated as semantic authority.
3. All false-pass risks are explicitly marked.
4. Handler-owned routing is labeled as pre-migration bridge debt.
5. Wrapper-graph passes are not used as conformance evidence.
6. Stale dot-paths carry zero implementation.
7. Live underscore paths are the only implementation targets.
8. Phase 3 migration claims are gated on M7 completion.
