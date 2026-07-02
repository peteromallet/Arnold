# M0 Decisions — Composition Spine Route Model & Ownership Freeze

Date: 2026-07-02
Status: frozen (planning-only; no runtime implementation)
Milestone: M0 — Decisions, Fixtures, and Protocol V0

## Posture

This document freezes the route-model decisions, public graph edge vocabulary,
ownership boundaries, and anti-scope terms for the Reigh Extension Composition
Spine epic (M0–M7b). It is a **durable planning artifact only**. No runtime
source, SDK symbol, test, script, or config file is created or edited by this
milestone.

Downstream milestones (M1a–M7b) cite this document as stable reference material
for contract language, edge discriminants, and ownership assignments.

Source of record: `.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md`
Locked Decisions (lines 35–49), M0 brief (`.megaplan/initiatives/reigh-extension-composition-spine-epic/m0-decisions-fixtures.md`),
and North Star constraints (`.megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md`).

## 1. Route-Model Decisions

### 1.1 Route Planning Architecture

Output-format and render-route planning stays on **typed route requirements,
route artifacts, and completion evidence**. Every route is scoped to one of the
four canonical `RenderRoute` values:

- `preview`
- `browser-export`
- `worker-export`
- `sidecar-export`

Source: `src/sdk/video/rendering/renderability.ts` line 2 (`RenderRoute` type);
`prep.md` line 49 (route-scope symmetry mandate).

### 1.2 Route-Scope Symmetry

Route-scope symmetry is mandatory. Missing, inferred, caller-dependent, or
ambiguous route scope is invalid. Omitted route scope MUST NOT be treated as
`all`.

Source: `prep.md` lines 49, 74 (locked decision and constraint);
`m0-decisions-fixtures.md` Locked Decisions line 1.

### 1.3 Determinism and Blockers

Every render route carries a `DeterminismStatus` (five values) and a set of
`RenderBlockerReason` values (nine values). No route may claim export support
based on preview behavior alone. Live/nondeterministic inputs MUST bake or
promote to durable materials/artifacts/captures before authoritative export.

Source: `src/sdk/video/rendering/renderability.ts` lines 22–27 (`DeterminismStatus`),
lines 40–49 (`RenderBlockerReason`); `prep.md` line 41 (nondeterministic input
constraint); `NORTHSTAR.md` line 16 (immutable constraint).

### 1.4 Material Status Model

Five core material statuses: `missing`, `pending`, `resolved`, `stale`, `failed`.
Detail taxonomy: `detail.phase` (queued, active, live-only), `detail.quality`
(weaker-provenance, route-incompatible). The planner material state in
`renderPlanner.ts` adds `unbaked` as a derived state.

Live-only, pending-active, stale, failed, weaker-provenance, or
route-incompatible material states MUST NOT be treated as generic
missing-package cases.

Source: `prep.md` line 42; `src/tools/video-editor/runtime/renderPlanner.ts`
`RenderPlannerMaterialState` type (line 33).

### 1.5 Planner Next Actions

V1 planner next actions: `select-route`, `materialize`, `bake`, `invoke-agent`,
`open-settings`, `install-extension`, `enable-extension`. M6 introduces
`start-process` as a process-family concern.

Source: `prep.md` line 43; `src/tools/video-editor/runtime/renderPlanner.ts`
`VideoEditorPlannerNextActionDescriptor`.

## 2. Public Graph Edge Vocabulary

The **public graph edge discriminants** for this entire epic are exactly four
names. No other edge discriminant is introduced into the public vocabulary
at any milestone.

| Edge | Semantics | Owning Milestone |
|------|-----------|-----------------|
| `consumes` | Shader material/resource consumption; graph-projected consumption edges from shader contributions to material refs | M1b (shader `consumes` projection becomes graph-authoritative) |
| `animates` | Keyframe-driven parameter animation; a contribution declares it animates a target parameter over time | M2 (target-path grammar and `animates`/`binds-live`) |
| `binds-live` | Live data binding to parameters/uniforms; a contribution declares it receives live runtime data bound to a target | M2 (target-path grammar and `animates`/`binds-live`) |
| `requires` | Graph-projected requirement edges; a contribution declares it requires another contribution, material, or artifact to be resolvable | M4 (graph-projected `requires` introduction); process repair executable only in M6 |

Source: `prep.md` lines 44–45 (locked decisions on edge vocabulary and
`requires` ownership); `m0-decisions-fixtures.md` Scope IN lines 1–3;
`NORTHSTAR.md` line 14 (graph authority constraint).

### 2.1 Semantic Boundaries

- `consumes` is owned by the shader fact-authority transition in M1b. It
  projects material/resource consumption from shader contributions into the
  composition graph.

- `animates` and `binds-live` are owned by the target-path and keyframe
  milestone (M2). They represent the two graph-visible parameter manipulation
  modes: keyframe interpolation and live runtime binding.

- `requires` is introduced as a graph-visible edge in M4 alongside shader
  assignment and shader-uniform keyframe integration. M3 may preserve
  declarative requirement payloads from earlier milestones, but M3 MUST NOT
  make `requires` a public graph edge discriminant. Process repair driven by
  `requires` edges becomes executable only in M6a.

Source: `prep.md` lines 44–45; `m0-decisions-fixtures.md` Locked Decisions
line 2.

## 3. Deferred Edge Names (Anti-Scope / Deferral)

The following edge-name concepts are **deferred for the entire epic**. They
MUST NOT appear as public graph edge discriminants in any milestone artifact,
SDK export, graph schema, planner state, or release assertion. They may appear
only in anti-scope or deferral prose (such as this section) to document the
explicit exclusion.

| Deferred Name | Reason for Deferral |
|---------------|-------------------|
| `materializes` | Agent/material-promotion path: M3c promotes agent-produced materials to durable `RenderMaterial`/`RenderArtifact` records, but the promotion is a host-internal operation, not a public graph edge. Making `materializes` a public edge would require a stable cross-family materialization protocol that is out of scope for this epic. |
| `produces` | Process output path: M6a/M7b handle process output and sidecar artifact production, but the production relationship is expressed through `process.result.attach` and route-artifact manifests, not through a public graph edge. A public `produces` edge would require a cross-family artifact-production contract that this epic defers. |
| `fallbacks` | Degradation/failover path: Fallback chains across contributions or routes require a stable degradation semantics and planner integration that is not part of the V1 composition SDK or any milestone in this epic. |

Source: `prep.md` line 44 (locked decision: "This epic does not add public
`materializes`, `produces`, or `fallbacks` edge discriminants"), lines 67–68
(constraints: no sandbox, marketplace, arbitrary material graphs);
`m0-decisions-fixtures.md` Scope IN line 2 (record deferred edge names).

### 3.1 Anti-Scope Constraint: No Public Deferred Edges

Per SD3 (settled decision from plan finalization): these three terms may appear
in anti-scope/deferral prose (as above) but MUST NOT appear in the public graph
edge vocabulary table (Section 2). Automated validators that check for literal
absence of these strings from all M0 artifacts must account for their required
presence in this deferral section. The contract is: they are excluded from the
**public edge vocabulary**, not deleted from all documentation.

## 4. Ownership Boundaries

### 4.1 Per-Milestone Artifact Ownership

| Artifact / Concern | Owning Milestone | Entry Condition |
|--------------------|-----------------|-----------------|
| Contribution identity (`extensionId, kind, contributionId`) | M1a | Portable refs, scoped identity, duplicate preservation |
| Composition graph projection (shader/ref fact authority) | M1b | Graph contracts, resolver states, `consumes` projection |
| Target-path grammar and validation | M2 | Grammar, schema capability, `animates`/`binds-live`, canonical diagnostics |
| Keyframe patch semantics (live/bake executable paths) | M3b | Bake live inputs to durable artifacts; execute graph-owned keyframe operations |
| Agent material promotion | M3c | Promote agent-produced masks/materials to `RenderMaterial`/`RenderArtifact` |
| Shader assignment execution and shader-uniform render-path integration | M4 | Execute shader assign/remove; integrate shader-uniform keyframes |
| `requires` edge introduction (graph-visible) | M4 | Declare graph-projected requirement edges; preserve declarative payloads from M3 |
| Process repair and `start-process` | M6a/M6b | Trusted process manager, lifecycle, `start-process` action mapping |
| Output-format route planning | M7a | Graph-backed route planning, route artifacts, typed manifest profiles |
| Sidecar/process execution for output-format routes | M7b | Wire sidecar execution to route planning; fourth composed example |

Source: `prep.md` lines 45–46 (ownership assignments), lines 46–47 (process
lifecycle exclusion from V1 SDK); `m0-decisions-fixtures.md` Locked Decisions
lines 2–3.

### 4.2 SDK vs. Host Boundary

- The V1 composition SDK (`src/sdk/index.ts`) exports portable contracts, types,
  and pure helpers only. It MUST NOT import from host runtime internals.

- Host-owned wiring (planner authority, graph projection, process manager,
  output-format routing) lives under `src/tools/video-editor/**`.

- `ExtensionRuntime` gains an additive contribution index. Existing family
  arrays remain source-compatible but stop being sufficient authority for a
  fact family after that family becomes graph-authoritative.

- Graph authority is fact-scoped, not global. Legacy fields MAY be normalized
  into graph facts but MUST NOT drive new planner/export behavior or release
  examples after the owning milestone lands.

Source: `prep.md` lines 35–38; `NORTHSTAR.md` line 14; `src/sdk/index.ts`.

### 4.3 Process and Output-Format Exclusion from V1 SDK

Process lifecycle states (8), process task result states, and sidecar route
vocabulary are process/output-format contracts introduced in M6/M7. They stay
**excluded from the V1 composition SDK surface**. The V1 SDK does not export
`ProcessSpec`, `ProcessLifecycleState`, or sidecar-route types.

Processes never mutate the timeline directly. Returned refs are recorded through
`process.result.attach`, then consumed through graph-owned material, media,
keyframe, or proposal patch operations.

Source: `prep.md` lines 47–48; `src/sdk/video/families/processes.ts` lines
31–129; `NORTHSTAR.md` lines 13, 17.

## 5. Target-Path Decisions

### 5.1 V1 Executable Target Paths

Exactly four target-path kinds are executable in V1:

- `clip-param`
- `effect-param`
- `transition-param`
- `shader-uniform`

Source: `prep.md` line 40; `NORTHSTAR.md` line 15.

### 5.2 Reserved (Non-Executable) Target Paths

The following are reserved for `extension-param` validation only and MUST
produce `composition/unsupported-target-kind` diagnostics in V1:

- `output`
- `process`
- `agent`
- `app`

Source: `prep.md` line 40.

## 6. Contribution Identity

Contribution identity defaults to **versionless lookup** by the tuple
`(extensionId, kind, contributionId)`. The `version` and `compatibilityRange`
fields constrain candidate selection **before** refs are persisted or accepted;
they do not form part of the identity key.

Source: `prep.md` line 39; `src/sdk/index.ts` lines 18–19 (exports
`ExtensionId`, `ContributionId`, `validateExtensionId`, `validateContributionId`
from `src/sdk/ids`).

## 7. Deterministic Capture Profiles (V1 Scope)

The first four deterministic-capture profiles in V1:

1. **Seed table** — fixed seed-driven deterministic captures for reproducible
   outputs.
2. **Event table** — event-driven capture sequences with known event schemas.
3. **Scalar table** — single-value scalar captures bound to parameters or
   uniforms.
4. **Structured motion curve table** — motion-curve keyframe captures with
   structured interpolation metadata.

All other capture/profile candidates are outside V1 scope. Expanding V1
deterministic capture beyond these four profiles requires release-example
evidence.

Event-table conversion becomes executable only through graph-owned keyframe
patch operations after M2 validation.

Source: `m0-decisions-fixtures.md` Locked Decisions lines 4–5; `prep.md`
lines 41–42.

## 8. Anti-Scope Terms (Exclusions and Deferrals)

The following concerns are **excluded from this entire epic**. They appear here
only as exclusions. No milestone artifact, SDK export, planner state, release
assertion, or composed example may depend on, reference, or imply these
concerns.

### 8.1 Never In This Epic

| Anti-Scope Term | Source |
|----------------|--------|
| Sandbox / permissions enforcement / code signing / permission broker | `prep.md` lines 67, 116; `NORTHSTAR.md` line 18 |
| Marketplace / package install / dependency manager / remote extension discovery | `prep.md` lines 67, 115; `NORTHSTAR.md` line 18 |
| Headless renderer / WebGPU renderer / visual graph editor | `prep.md` lines 67, 117; `NORTHSTAR.md` line 18 |
| Shader stacks / FBO chains / arbitrary texture routing / arbitrary material graphs | `prep.md` lines 67, 117; `NORTHSTAR.md` line 18 |
| Public `materializes`, `produces`, or `fallbacks` edge discriminants | `prep.md` line 44, 118 |
| Process/output/agent/app executable V1 target paths | `prep.md` lines 40, 68, 119 |
| Arbitrary multi-process DAGs | `prep.md` line 120 |
| Untrusted or remote process execution | `prep.md` line 121 |
| Hardcoded physical-device support, sandbox safety, executable-package preview, or runtime-safety claims for machine-path or executable-package artifact profiles | `prep.md` line 75 |
| Expanding V1 deterministic capture beyond seed/event/scalar/motion-curve tables without release-example evidence | `prep.md` line 76; `m0-decisions-fixtures.md` Constraints line 3 |
| Docs or examples claiming support beyond graph/planner/schema/runtime evidence | `prep.md` line 122 |

### 8.2 Deferred Edge Names (Public Vocabulary Exclusion)

The terms `materializes`, `produces`, and `fallbacks` are deferred for the
entire epic. They MUST NOT appear as public graph edge discriminants. See
Section 3 for full deferral rationale.

## 9. Decision Traceability

Every decision in this document traces to a stable repo source. The primary
sources are:

- `.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md` —
  Locked Decisions (lines 35–49), Constraints (lines 63–75), Anti-Scope
  (lines 111–122), Done Criteria (lines 124–132).

- `.megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md` —
  Immutable constraints (lines 13–18).

- `.megaplan/initiatives/reigh-extension-composition-spine-epic/m0-decisions-fixtures.md` —
  Scope IN/OUT (lines 13–28), Locked Decisions (lines 30–36), Constraints
  (lines 38–44).

- `src/sdk/video/rendering/renderability.ts` — `RenderRoute` (line 2),
  `DeterminismStatus` (lines 22–27), `RenderBlockerReason` (lines 40–49).

- `src/tools/video-editor/runtime/renderPlanner.ts` —
  `RenderPlannerMaterialState` (line 33),
  `VideoEditorPlannerNextActionDescriptor`.

- `src/sdk/video/families/processes.ts` — `ProcessSpec`, `ProcessLifecycleState`
  (8 states, lines 31–129).

- `src/sdk/index.ts` — Public SDK barrel; extension identity exports (lines
  18–19).

- `config/extensions/family-maturity.json` — 21-family declaration/execution
  maturity snapshot.

- `docs/extensions/phase4-readiness.md` — Phase 4 promotion checklist, render
  planner participation contract, trust posture.

- `docs/extensions/foundation-closure-assessment.md` — M4 closure gate,
  satisfied contracts, family maturity snapshot.

No claim in this document depends solely on the absent v8 architecture brief
(`.megaplan/briefs/reigh-extension-composition-spine-plan-elegant-v8.md`).

## 10. Relationship to Other M0 Artifacts

| Artifact | Relationship |
|----------|-------------|
| `README.md` | Indexes this artifact; defines static validation checklist including edge-vocabulary grep checks |
| `v8-architecture-baseline.md` | Provides the reconstructed architecture context; this document freezes the decisions within that context |
| `m0-fixture-matrices.md` | Fixture rows that enumerate every literal in the cited SDK unions, config arrays, process contracts, artifact contracts, and render planner authority |
| `m0-release-examples.md` | Four graph-backed composed examples; each cites the edge vocabulary and ownership boundaries frozen here |
| `deterministic-capture-profiles.md` | Details the four V1 capture profiles listed in Section 7 |
| `json-rpc-protocol-v0.md` | Drafts the process protocol whose lifecycle states and error classes are scoped to M6a, consistent with the ownership boundaries in Section 4 |
