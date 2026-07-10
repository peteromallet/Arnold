# V8 Architecture Baseline — Reigh Extension Composition Spine

Date: 2026-07-01
Status: reconstructed from surviving source artifacts (original v8 brief is absent)

## Provenance Statement

The original v8 architecture brief for this epic is **absent** from the repository.
The expected path was:

```
.megaplan/briefs/reigh-extension-composition-spine-plan-elegant-v8.md
```

This file was authored in a private workspace
(`/Users/peteromalley/Documents/.megaplan-worktrees/reigh-pristine-sdk-boundary-run`)
and was **not transferred** to the target repository (source: `.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md` line 5).

This document reconstructs the v8 architecture baseline from the collective state of
the following surviving artifacts. Every major claim is annotated with its
reconstructive source path. No claim depends solely on the absent v8 brief.

## Reconstructive Sources

| # | Source | Path | Role |
|---|--------|------|------|
| 1 | prep.md | `.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md` | Primary reconstruction artifact: 13-milestone epic chain, 44 locked decisions, constraints, open questions, anti-scope |
| 2 | NORTHSTAR.md | `.megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md` | Immutable constraints, success definition |
| 3 | M0 milestone brief | `.megaplan/initiatives/reigh-extension-composition-spine-epic/m0-decisions-fixtures.md` | M0 scope, decisions, done criteria |
| 4 | M1a–M7b milestone briefs | `.megaplan/initiatives/reigh-extension-composition-spine-epic/{m1a-*,m1b-*,m2-*,m3a-*,m3b-*,m3c-*,m4-*,m5-*,m6a-*,m6b-*,m7a-*,m7b-*}.md` | Per-milestone scope, ownership, and acceptance |
| 5 | family-maturity.json | `config/extensions/family-maturity.json` | 21-family declaration/execution maturity snapshot |
| 6 | SDK contract surface | `src/sdk/index.ts` | 153-line public barrel: 30+ exported families, stable types |
| 7 | contributionKinds.ts | `src/sdk/video/families/contributionKinds.ts` | Authoritative `VideoContributionKind` union (21 members) |
| 8 | processes.ts | `src/sdk/video/families/processes.ts` | Process family contracts: `ProcessSpec`, `ProcessLifecycleState` (8 states) |
| 9 | artifacts.ts | `src/sdk/video/rendering/artifacts.ts` | `RenderMaterial`, `RenderArtifact`, `RenderArtifactManifest`, `BakeContract` |
| 10 | renderability.ts | `src/sdk/video/rendering/renderability.ts` | `RenderRoute`, `DeterminismStatus`, `RenderBlockerReason`, and their locked const arrays |
| 11 | capabilities.ts | `src/sdk/video/rendering/capabilities.ts` | Shader materializer requirement scope |
| 12 | renderPlanner.ts | `src/tools/video-editor/runtime/renderPlanner.ts` | Canonical render/export readiness reducer: route plans, planner blockers, diagnostics, next actions, guard-scan adaptation |
| 13 | phase4-readiness.md | `docs/extensions/phase4-readiness.md` | Phase 4 promotion checklist, render planner participation contract, trust posture |
| 14 | foundation-closure-assessment.md | `docs/extensions/foundation-closure-assessment.md` | M4 closure gate, satisfied contracts, family maturity snapshot |
| 15 | process-example.ts | `src/examples/process-example.ts` | Process contribution declaration example |

## Immutable Constraints (North Star)

From `NORTHSTAR.md` (`.megaplan/initiatives/reigh-extension-composition-spine-epic/NORTHSTAR.md`):

1. **Extensions and processes never mutate raw timeline internals directly.**
2. **The graph is the authority for graph-authoritative fact families;** legacy fields are compatibility inputs only.
3. **V1 target paths are limited to `clip-param`, `effect-param`, `transition-param`, and `shader-uniform`.**
4. **Live or nondeterministic inputs must bake or promote to durable materials/artifacts/captures before authoritative export.**
5. **Trusted process runtime and output-format sidecars are real, but they stay namespaced outside the V1 composition SDK.**
6. **No sandbox, marketplace, headless renderer, WebGPU, arbitrary material graphs, shader stacks, FBO chains, or generic texture routing in this epic.**

## What We Are Building (North Star)

A unified composition spine for Reigh extensions. Clips, shaders, effects, transitions,
live data, agent-produced materials, and output formats all participate through a
host-projected `CompositionGraph` of contribution refs, typed target paths, graph edges,
route requirements, and artifact manifests.

## Epic Architecture

### Epic Chain (13 Milestones)

From `prep.md` (lines 19–31):

| Milestone | Name | Summary |
|-----------|------|---------|
| M0 | Decisions, Fixtures, and Protocol V0 | Freeze route model, ownership boundaries, capture profiles, release examples, fixture matrices, and process protocol v0 |
| M1a | Reference Identity, Patch Vocabulary, First Validation Rule | Portable refs, scoped contribution identity, duplicate preservation, reserved patch ops, shader-scope validation |
| M1b | Composition Graph Projection Becomes Shader/Ref Fact Authority | Graph contracts, resolver states, shader `consumes` projection, patch preview, graph-first planner authority |
| M2 | Target Paths, Schema Capability, Keyframes, and Live Binding | Target-path grammar, schema capability, `animates`/`binds-live`, canonical target diagnostics |
| M3a | Material Status and Planner Matrix | Five-status material model, status details, predicates, planner matrix, next actions, provenance validation |
| M3b | Live Binding and Deterministic Capture | Bake live inputs to durable artifacts/captures, execute graph-owned keyframe operations |
| M3c | Agent Material Promotion | Promote agent-produced masks/materials to durable `RenderMaterial`/`RenderArtifact` records |
| M4 | Clip Type, Shader, and Shader-Uniform Keyframes | Shader assign/remove, shader-uniform keyframes, graph-projected `requires`, clip + shader example |
| M5 | Effects, Transitions, Live Data, and Agent Mask Material | Effect live binding, transition mask material consumption; first three V1 composed examples |
| M6a | Process Runtime Core | Trusted process manager, JSON-RPC stdio protocol, lifecycle vocabulary, runtime overlays |
| M6b | Process UX and Canary | Process dashboard/repair UI, `start-process` action mapping, canary coverage, browser acceptance |
| M7a | Output-Format Route Planning | Graph-backed output-format route planning, route artifacts, typed manifest profiles |
| M7b | Output-Format Sidecar Integration | Wire sidecar/process execution to output-format route planning, fourth composed example |

### Phasing

- **M0**: Planning artifacts only — no runtime implementation (source: `m0-decisions-fixtures.md` Execution Posture).
- **M1–M5**: V1 composition SDK and first three graph-backed release examples without legacy-only planner authority (source: `prep.md` Done Criteria).
- **M6–M7**: Trusted process runtime and output-format sidecar route planning outside the V1 composition SDK; fourth composed example (source: `prep.md` Done Criteria).

## Core Architecture Decisions

### Contribution Identity

From `prep.md` Locked Decisions (lines 39–40) and `src/sdk/index.ts`:

- Contribution identity defaults to **versionless lookup by `(extensionId, kind, contributionId)`**.
- `version` and `compatibilityRange` constrain candidate selection before refs are persisted or accepted.
- Source: `prep.md` line 39; SDK exports `ExtensionId`, `ContributionId`, `validateExtensionId`, `validateContributionId` from `src/sdk/ids` (see `src/sdk/index.ts` lines 18–19).

### Target Path Vocabulary

From `prep.md` Locked Decisions (line 40) and `NORTHSTAR.md` (line 16):

- **V1 executable target paths**: `clip-param`, `effect-param`, `transition-param`, `shader-uniform`.
- **Reserved (non-executable in V1)**: `output`, `process`, `agent`, `app` — validate only through `extension-param` with `composition/unsupported-target-kind`.
- Source: `prep.md` line 40; `NORTHSTAR.md` line 16.

### Public Graph Edge Vocabulary

From `prep.md` Locked Decisions (lines 43–44) and `m0-decisions-fixtures.md` Scope:

- **Four public edge discriminants**: `consumes`, `animates`, `binds-live`, `requires`.
- `consumes` — shader material/resource consumption (M1b ownership).
- `animates` — keyframe-driven parameter animation (M2 ownership).
- `binds-live` — live data binding to parameters/uniforms (M2 ownership).
- `requires` — graph-projected requirement edges (M4 ownership; process repair executable only in M6).

**Deferred edge names** (`materializes`, `produces`, `fallbacks`) are excluded from
the public edge vocabulary for the entire epic. They may appear only in anti-scope
or deferral prose, never as public graph edge discriminants.
Source: `prep.md` line 44; `m0-decisions-fixtures.md` Scope IN line 2.

### Ownership Boundaries

From `prep.md` Locked Decisions (lines 45–46) and `m0-decisions-fixtures.md` Locked Decisions:

| Artifact | Owning Milestone |
|----------|-----------------|
| CompositionGraph projection, `consumes` edge, shader/ref authority | M1b |
| Target-path grammar and validation | M2 |
| Keyframe patch semantics (live/bake paths) | M3b |
| Shader assignment execution and shader-uniform render-path integration | M4 |
| `requires` edge introduction | M4 |
| Process repair and `start-process` | M6 |
| Output-format route planning | M7a |
| Sidecar/process execution for output-format routes | M7b |

### M1b Scope: Composition Graph Projection — Shader/Ref Authority

M1b makes `CompositionGraph` projection the **authoritative** source for shader/ref
facts and contribution-index lookups. When a `CompositionGraph` is present on
`ExtensionRuntime`, it replaces — not supplements — legacy shader summaries and
direct contribution-index access for all M1b-owned fact families.

#### What M1b Owns

| Surface | Description |
|---------|-------------|
| `consumes` edges | The only public edge kind in M1b. A source node (clip or timeline-postprocess) consumes a shader contribution from a target contribution node. |
| Shader reference resolution | All 10 resolver states (`resolved`, `missing`, `disabled`, `inactive-reserved`, `invalid-package`, `duplicate`, `settings-error`, `runtime-error`, `version-incompatible`, `unknown`) with locked precedence: package failures before inactive/reserved before resolved. |
| Composition diagnostics | Canonical `composition/` diagnostic codes with structured detail fields (`nodeId`, `refKey`, `refState`, `scope`, `extensionId`, `contributionId`, `shaderId`). |
| Graph preview | Internal `shader.assign` and `shader.remove` preview operations applied to a cloned graph; returns updated nodes, edges, reference states, and diagnostics without mutating the original. |
| Graph-first planner authority | `planRender` derives shader materializer requirements and scope validation from graph nodes/edges/reference states when a graph is present. |
| Graph-first export scan input | `scanExportConfig` derives guard scanner findings from graph-resolved facts when a graph is present; `buildExportReadinessPlan()` feeds those findings to `planRender()`. |
| Graph-first shader validation | `validateShaderComposition` derives projected shaders and first-wins occupancy from graph edges when a graph is present. |

#### Legacy Inputs: Compatibility Sources Only

Legacy `TimelineShaderSummary[]`, `ContributionIndex`, and descriptor arrays remain
in the runtime surface for **graph-absent compatibility callers**, but they are
**not alternate authority** for M1b-owned facts:

- Graph-present planner calls **ignore** legacy snapshot shader refs and derive all
  shader/ref facts from the graph.
- Graph-present export guard calls do **not** read legacy timeline shader metadata.
- Graph-present shader validation does **not** consult legacy shader summaries or
  direct contribution-index candidates.
- Graph-absent callers continue to work through legacy paths but emit a
  **compatibility warning** diagnostic.

Legacy descriptor arrays (e.g. `VideoEditorShaderDescriptor[]`) remain populated
for existing consumers but are derived from the graph when one is present, ensuring
they cannot become a second authority pathway.

#### Out of Scope for M1b

The following surfaces are **explicitly out of scope** for M1b and belong to later
milestones or are excluded from the entire epic:

| Surface | Owner / Status |
|---------|---------------|
| Target paths (`clip-param`, `effect-param`, `transition-param`, `shader-uniform`) | M2 |
| `animates` edges (keyframe-driven parameter animation) | M2 |
| `binds-live` edges (live data binding) | M2 |
| `requires` edges (graph-projected requirements) | M4 |
| Material statuses (`missing`, `pending`, `resolved`, `stale`, `failed`) | M3a |
| Live material promotion (bake live inputs to durable artifacts) | M3b |
| Agent material promotion (promote masks/materials to `RenderMaterial`) | M3c |
| Process vocabularies (lifecycle, JSON-RPC protocol, runtime overlays) | M6a/M6b |
| Output-format vocabularies (route artifacts, manifest profiles, sidecars) | M7a/M7b |
| `materializes`, `produces`, `fallbacks` edge discriminants | Excluded from entire epic |
| Node kinds beyond `clip`, `timeline-postprocess`, `contribution` | Later milestones |
| Public `shader.assign` / `shader.remove` SDK patch families | Excluded from entire epic |

### M1b Composition Graph Contracts

#### Node Kinds

M1b supports exactly three node kinds:

- `clip` — a timeline clip (shader-assignable scope).
- `timeline-postprocess` — the timeline-wide postprocess scope.
- `contribution` — a contribution declared by an extension (shader, effect, parser, etc.).

These are exposed as the `COMPOSITION_NODE_KINDS` constant in the SDK barrel and are
the only node kinds for M1b graph authority. Future milestones may add nodes for
tracks, outputs, processes, and other surfaces.

#### Edge Kinds

The composition graph now supports four public edge kinds (M1b–M4):

- `consumes` — a source node (clip or timeline-postprocess) consumes a shader
  contribution from a target contribution node.
- `animates` — keyframe-driven parameter animation for clip-type parameters and
  shader-uniform target paths (`uniforms.<name>`).
- `binds-live` — live data binding to parameters/uniforms.
- `requires` — graph-projected requirement edges with typed route requirement
  detail (subject, route scope, satisfier kind, determinism, fallback allowance,
  repair action). Process repair driven by `requires` edges is executable in M6.

These are exposed as the `COMPOSITION_EDGE_KINDS` constant in the SDK barrel.
Deferred edge names (`materializes`, `produces`, `fallbacks`) are excluded from
the public edge vocabulary for the entire epic.

#### Resolver States

The M1b resolver produces exactly 10 reference states with locked precedence:

| Precedence | State | Meaning |
|-----------|-------|---------|
| 1 (highest) | `invalid-package` | Package marked invalid by the loader |
| 2 | `settings-error` | Package loaded but settings migration failed |
| 3 | `runtime-error` | Package loaded but runtime activation error |
| 4 | `version-incompatible` | Package incompatible with current host version |
| 5 | `disabled` | User-disabled package |
| 6 | `duplicate` | Exact scoped-key duplicate (first-wins loser) |
| 7 | `inactive-reserved` | Kind not yet bridged in this runtime |
| 8 | `missing` | No scoped candidate exists in the index |
| 9 | `unknown` | Fallback for unrecognised states |
| 10 (lowest) | `resolved` | Valid, active, package-healthy contribution ref |

**Critical semantics**: `missing` is defined **only** as zero scoped candidates.
It is never used when candidates exist but are in a non-resolved state. Package-failure
states classify before inactive/reserved states, and all non-resolved states classify
before `resolved`.

### Material Status Model

From `prep.md` Locked Decisions (line 42) and `src/tools/video-editor/runtime/renderPlanner.ts`:

- **Five core material statuses**: `missing`, `pending`, `resolved`, `stale`, `failed`.
- **Detail taxonomy**: `detail.phase` (queued, active, live-only), `detail.quality` (weaker-provenance, route-incompatible).
- **Planner material state** (renderPlanner.ts): `missing`, `stale`, `resolved`, `unbaked`.
- Source: `prep.md` line 42; `renderPlanner.ts` `RenderPlannerMaterialState` type (line 33).

### Render Planner Next Actions

From `prep.md` Locked Decisions (line 43) and `renderPlanner.ts`:

- **V1 planner next actions**: `select-route`, `materialize`, `bake`, `invoke-agent`, `open-settings`, `install-extension`, `enable-extension`.
- **M6 introduces**: `start-process` (process-family concern).
- Source: `prep.md` line 43; `renderPlanner.ts` `VideoEditorPlannerNextActionDescriptor`.

### Determinism Status

From `src/sdk/video/rendering/renderability.ts` (lines 22–27):

| Status | Meaning |
|--------|---------|
| `deterministic` | Same inputs produce equivalent outputs |
| `preview-only` | Usable only for interactive preview |
| `live-unbaked` | Depends on live provider/runtime state |
| `process-dependent` | Depends on external process/tool versions |
| `unknown` | Insufficient metadata; guards stay conservative |

### Render Blocker Reasons

The canonical blocker vocabulary is the `RenderBlockerReason` union and
`RENDER_BLOCKER_REASONS` const array in
`src/sdk/video/rendering/renderability.ts`. Architecture docs should cite that
source and the planner mappings in `src/tools/video-editor/runtime/renderPlanner.ts`
rather than maintaining a copied literal list.

### Export Readiness Authority

Export readiness is planner-owned. Guard scans, router/provider checks, and
output-format diagnostics may contribute structured inputs, but `planRender()`
is the final reducer and planner `RenderBlocker` records are the canonical
user-facing readiness vocabulary. `buildExportReadinessPlan()` is a thin adapter
that passes `scanExportConfig()` payloads into the planner instead of computing
an independent blocked/unblocked decision. Original `export/*` diagnostic codes
are preserved in finding detail for diagnostics and debugging; they are
diagnostic metadata, not readiness authority.

### Render Routes

From `src/sdk/video/rendering/renderability.ts` (line 2):

`preview`, `browser-export`, `worker-export`, `sidecar-export`.

## Family Maturity Snapshot

From `config/extensions/family-maturity.json` (827 lines, 21 entries) and
`docs/extensions/phase4-readiness.md` family maturity table:

| Family | Declaration | Execution | Trusted | Bridged | Key Notes |
|--------|------------|-----------|---------|---------|-----------|
| Slot | documented | public-supported | No | Yes | Only fully conformant family (gapCount: 0) |
| Dialog | documented | host-integrated | No | Yes | Bridged at M1 |
| Panel | documented | host-integrated | No | Yes | Bridged at M1 |
| Inspector Section | documented | host-integrated | No | Yes | Bridged at M1 |
| Timeline Overlay | documented | host-integrated | No | Yes | Bridged at M2 |
| Command | documented | host-integrated | No | Yes | Bridged at M4 |
| Keybinding | documented | host-integrated | No | Yes | Bridged at M4 |
| Context Menu Item | documented | host-integrated | No | Yes | Bridged at M4 |
| Clip Type | schema-backed | runtime-bridged | No | Yes | Host-owned keyframe interpolation |
| Automation | schema-backed | runtime-bridged | No | Yes | Built-in clip type, bridged at M9 |
| Metadata Facet | schema-backed | runtime-bridged | No | Yes | Bridged at M6 |
| Effect | schema-backed | delegated | No | Yes | Preview-only; export blocked unless allowBrowserExport/allowWorkerExport |
| Transition | schema-backed | delegated | No | Yes | Preview-only; export blocked unless allowBrowserExport/allowWorkerExport |
| Shader | schema-backed | delegated | No | Yes | WebGL materializer; bridged at M13 |
| Asset Detail Section | schema-backed | delegated | No | Yes | Bridged at M6 |
| Parser | schema-backed | delegated | No | Yes | Asset ingestion pipeline, bridged at M6 |
| Agent Tool | schema-backed | delegated | Yes | Yes | Host-mediated, proposal-backed |
| Agent | typed | delegated | Yes | No | No standalone host adapter |
| Output Format | typed | delegated | No | Yes | Runtime execution reserved |
| Process | typed | delegated | Yes | Yes | Execution reserved for M12 |
| Search Provider | typed | delegated | No | Yes | Execution reserved, bridged at M6 |

Source: `config/extensions/family-maturity.json`; snapshot also present in
`docs/extensions/phase4-readiness.md` and `docs/extensions/foundation-closure-assessment.md`.

## Process Family Architecture

From `src/sdk/video/families/processes.ts` and `prep.md`:

- **Protocol**: `ProcessSpec.protocol: 'stdio-jsonrpc'` — newline-delimited JSON-RPC 2.0 over stdio.
- **Lifecycle states** (8): `not-installed`, `stopped`, `starting`, `ready`, `busy`, `degraded`, `failed`, `stopping`.
- **ProcessSpec fields**: `spawn` (command, args, env, cwd), `healthCheck`, `shutdown`, `restartPolicy`, `version`, `env` (typed field specs), `operations`, `capabilities`, `requiredBy`.
- **Processes never mutate the timeline directly.** Returned refs are recorded through `process.result.attach`, then consumed through graph-owned material, media, keyframe, or proposal patch operations.
- Source: `processes.ts` lines 31–129; `prep.md` line 48.

## Output-Format Architecture

From `prep.md` and `m0-decisions-fixtures.md`:

- Output-format route planning stays on **typed route requirements, route artifacts, and completion evidence**.
- Route-scope symmetry is mandatory: missing, inferred, caller-dependent, or ambiguous route scope is invalid.
- Source: `prep.md` line 49; `m0-decisions-fixtures.md` Locked Decisions line 1.

## SDK Boundary

From `src/sdk/index.ts` (153 lines) and `docs/extensions/foundation-closure-assessment.md`:

- `@reigh/editor-sdk` (`src/sdk/index.ts`) is the extension author surface.
- Host-owned wiring lives under `src/tools/video-editor/**`.
- SDK exports portable contracts, types, and pure helpers only; it must not import from host internals.
- Contribution families declare `declarationMaturity` and `executionMaturity` in `config/extensions/family-maturity.json`.

## Trust Posture

From `docs/extensions/phase4-readiness.md` and `docs/extensions/foundation-closure-assessment.md`:

- Extension code runs as **trusted, unsandboxed code** in the host environment.
- Manifest permissions are **declarative metadata only**; they are not runtime enforcement, sandbox isolation, code signing, or a permission broker.
- No marketplace, remote install, or signing claims.

## Four Composed Examples

From `prep.md` Outcome (lines 9–10):

1. **Clip + Shader + Shader-Uniform Keyframes** (M4): Shader assignment/removal, shader-uniform keyframe integration, graph-projected `requires` edge.
2. **Effect + Live Data + Bake** (M5): Effect live binding, live data bake to deterministic captures, parameter targeting.
3. **Transition + Agent-Produced Mask Material** (M5): Transition mask material consumption, agent material promotion to durable `RenderMaterial`.
4. **Output Format + Sidecar/Process Dependency** (M7b): Non-video artifact output, sidecar/process execution wired to output-format route planning.

## Anticipated Release Gates

From `prep.md` Done Criteria (line 132):

Release gates enforce:
- SDK exports
- Family maturity
- Graph participation
- Route claims
- Material statuses
- Deterministic captures
- Process-backed live sources
- Sidecar blockers
- Typed non-video artifacts
- Multi-artifact route completion
- Docs capability claims
- Graph-path markers
- Example readiness
- Browser acceptance (where UI exists)

## Anti-Scope (Never In This Epic)

From `prep.md` Anti-Scope and Constraints (lines 67–75, 112–122):

- No runtime implementation in planning artifacts (M0).
- No marketplace, package install, dependency manager, or remote extension discovery.
- No sandbox or permissions enforcement.
- No headless renderer, WebGPU renderer, visual graph editor, shader stack, arbitrary texture routing, FBO chain, or arbitrary material graph.
- No public `materializes`, `produces`, or `fallbacks` edge discriminants.
- No process/output/agent/app executable V1 target paths.
- No arbitrary multi-process DAGs.
- No untrusted or remote process execution.
- No hardcoded physical-device support, sandbox safety, executable-package preview, or runtime-safety claims for machine-path or executable-package artifact profiles.
- No expanding V1 deterministic capture beyond seed table, event table, scalar table, and structured motion curve table without release-example evidence.

## Open Questions (Carried from prep.md)

From `prep.md` Open Questions (lines 53–60):

- Where should Phase 0 decision records and fixture inventories live durably?
- Should the non-media bake concept be named `DeterministicCapture` or `BakedValueRef`?
- Which existing canaries are the canonical seeds for the four release examples?
- Where is the least invasive host boundary for `ExtensionRuntime.contributionIndex` assembly?
- Which existing inspector/export/status surfaces should host blocker and repair UI?
- How should the sequential chain handle v8 parallelization notes (M3a/M3b, M3c/M4, M7a/M6b)?
- What repo-controlled fixture process should M6 use, and where should JSON-RPC protocol fixtures live?
- Which governance scripts already exist vs. need to be created in M7b?
