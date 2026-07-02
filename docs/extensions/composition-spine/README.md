# Composition Spine — M0 Planning Artifacts

Date: 2026-07-01
Milestone: M0 — Decisions, Fixtures, and Protocol V0
Status: planning-only (no runtime implementation, no test execution)

## Posture

M0 is a **documentation-only milestone**. It produces durable planning artifacts
that downstream milestones (M1a through M7b) cite as stable reference material.
No runtime source, SDK export, test, script, UI, or config file is created or
edited by this milestone. Validation is static review, grep checks, source
cross-referencing, and diff hygiene — not test execution.

The sole allowed write surface is `docs/extensions/composition-spine/**`.

## Missing V8 Brief Source

The original v8 architecture brief for the composition spine is absent from the
repository. The expected path is:

```
.megaplan/briefs/reigh-extension-composition-spine-plan-elegant-v8.md
```

The downstream `v8-architecture-baseline.md` artifact reconstructs the baseline
from surviving sources: `prep.md` (at
`.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md`), North
Star constraints, milestone briefs,
`config/extensions/family-maturity.json`, SDK contract files, supported/deferred
behavior matrices, and cited source paths. All claims in the reconstruction cite
verifiable repo sources rather than asserting the missing brief's contents.

## Artifact Index

The seven M0 artifacts, in dependency order:

| # | Artifact | Description |
|---|----------|-------------|
| 1 | `README.md` | This index: M0 posture, v8 brief gap, changed surface, artifact registry, path selectors, and static validation checklist. |
| 2 | `v8-architecture-baseline.md` | Reconstructed v8 architecture baseline from `prep.md`, North Star constraints, milestone briefs, `family-maturity.json`, SDK contracts, and behavior matrices. Cites all reconstructive sources; explicitly records the missing original brief. |
| 3 | `m0-decisions.md` | Frozen route-model decisions, public graph edge vocabulary (`consumes`, `animates`, `binds-live`, `requires`), ownership boundaries (M2/M3b/M4/M6), deferred edge names in anti-scope prose only, and anti-scope term exclusions. |
| 4 | `m0-fixture-matrices.md` | Fixture rows for every literal in the cited SDK unions, config arrays, process contracts, artifact contracts, and render planner authority. Cross-references `src/tools/video-editor/runtime/renderPlanner.ts`. |
| 5 | `m0-release-examples.md` | The four graph-backed composed examples with graph-path assertions, fixture row references, UI surface markers, release gates, and owning milestone alignment. |
| 6 | `deterministic-capture-profiles.md` | Exactly four V1 capture profiles (`seed table`, `event table`, `scalar table`, `structured motion curve table`) with required evidence and usable release examples. All other capture/profile candidates marked outside V1. |
| 7 | `json-rpc-protocol-v0.md` | Newline-delimited JSON-RPC 2.0 over stdio for `ProcessSpec.protocol: 'stdio-jsonrpc'`. Names methods, message types, lifecycle states, correlation fields, and error classes. M0 implements no process manager or sidecar runtime. |

## Changed Surface

```
docs/extensions/composition-spine/**
```

No other paths are modified by M0.

## Path Selectors

The seven concrete path selectors for this milestone, listed verbatim:

1. `docs/extensions/composition-spine/README.md`
2. `docs/extensions/composition-spine/v8-architecture-baseline.md`
3. `docs/extensions/composition-spine/m0-decisions.md`
4. `docs/extensions/composition-spine/m0-fixture-matrices.md`
5. `docs/extensions/composition-spine/m0-release-examples.md`
6. `docs/extensions/composition-spine/deterministic-capture-profiles.md`
7. `docs/extensions/composition-spine/json-rpc-protocol-v0.md`

These are the only files M0 creates or edits. Static validation commands
(`git diff --check`, `rg`/`grep` checks, `git diff --name-only`) are validation
tools applied against these selectors — they are not themselves selectors and
are not included in selector metadata.

## Static Command Checklist

M0 validation is static only. No runtime tests are executed. Run these commands
in sequence to validate all M0 artifacts against the decision and fixture
baselines recorded in this milestone.

- [ ] `git diff --name-only` shows only `docs/extensions/composition-spine/**`.
- [ ] `git diff --check -- docs/extensions/composition-spine` reports no whitespace errors.
- [ ] `rg 'consumes|animates|binds-live|requires' docs/extensions/composition-spine/` confirms the four public edge discriminants appear in the decision record.
- [ ] `rg 'materializes|produces|fallbacks' docs/extensions/composition-spine/` confirms deferred edge names appear only in anti-scope or deferral prose, never in the public edge vocabulary table.
- [ ] `rg 'sandbox|marketplace|permission.enforcement|headless.renderer|WebGPU|arbitrary.material.graph|shader.stack|FBO.chain|generic.texture.routing' docs/extensions/composition-spine/` confirms anti-scope terms are exclusions or deferrals only.
- [ ] `rg 'seed.table|event.table|scalar.table|structured.motion.curve.table' docs/extensions/composition-spine/deterministic-capture-profiles.md` confirms exactly four V1 profiles.
- [ ] `rg 'health|execute|cancel|shutdown' docs/extensions/composition-spine/json-rpc-protocol-v0.md` confirms the four required methods.
- [ ] `rg 'progress|log|result|error' docs/extensions/composition-spine/json-rpc-protocol-v0.md` confirms the four message types.
- [ ] `rg 'protocol-error|timeout|process-exited|invalid-request' docs/extensions/composition-spine/json-rpc-protocol-v0.md` confirms the four error classes.
- [ ] Every architecture and fixture claim cites a stable repo source path (SDK file, config file, runtime source); no claim depends solely on the absent v8 brief.

## Anti-Scope Review Guidance

Review each M0 artifact for the following anti-scope violations, which are
explicitly excluded or deferred from M0:

- **Deferred edge names** (`materializes`, `produces`, `fallbacks`): Must appear
  only in anti-scope/deferral prose or the deferred section of `m0-decisions.md`.
  They must never be listed as public graph edge discriminants, nor appear in
  fixture matrix row definitions, nor be claimed as M0-deliverable vocabulary.
  If any of these strings appear outside approved deferral context, fix the
  wording to move them into anti-scope prose — do not delete the required
  deferral record.
- **Anti-scope domains** (`sandbox`, `marketplace`, `permission.enforcement`,
  `headless.renderer`, `WebGPU`, `arbitrary.material.graph`, `shader.stack`,
  `FBO.chain`, `generic.texture.routing`): Must appear only as exclusions or
  deferrals. If any of these are presented as M0 scope, rewrite as explicit
  exclusions.
- **V1 capture/profile overreach**: `deterministic-capture-profiles.md` must
  list exactly four V1 profiles. If any additional profile name (e.g.,
  `histogram`, `frame-sampled`, `audio-amplitude`, `binary blob`, `array table`)
  appears outside a "deferred" or "explicitly out of V1 scope" annotation, mark
  it as out-of-V1.
- **M0 runtime claims**: No artifact may describe M0 as implementing a process
  manager, sidecar runtime, stdout/stderr pipe, or JSON-RPC wire handler. The
  protocol document must state that M0 implements no process manager.
- **Missing source citations**: Every architecture claim must cite a verifiable
  repo path (e.g., SDK file, config file, runtime source). Claims that rest
  solely on the absent v8 brief are invalid.

## No-Runtime-Tests Rule

M0 is a **documentation-only milestone**. The following are strictly prohibited
within M0 scope:

- Running `jest`, `vitest`, `playwright`, or any other test runner against the
  repository.
- Writing new test files (`*.test.ts`, `*.test.tsx`, `*.spec.ts`, etc.) under
  any directory.
- Modifying existing test files, including fixture data, mock factories, or
  test harness configuration.
- Creating or editing SDK exports, runtime source files, configuration files,
  build scripts, or UI components.
- Executing `npx`, `pnpm`, `yarn`, or `node` against source files for
  validation purposes (static grep/diff checks are the only allowed validation).

Validation is performed exclusively through: `git diff`, `git diff --check`,
`rg`/`grep` pattern checks, `wc -l` line counts, `nl -ba` source inspection,
and manual diff review. If a check requires running code to verify, it is out
of M0 scope.

## Final Reviewer Checklist

Before signing off on M0, confirm each item:

- [ ] All seven path selectors (`README.md`, `v8-architecture-baseline.md`,
  `m0-decisions.md`, `m0-fixture-matrices.md`, `m0-release-examples.md`,
  `deterministic-capture-profiles.md`, `json-rpc-protocol-v0.md`) exist and
  are non-empty.
- [ ] `git diff --name-only` reports no files outside
  `docs/extensions/composition-spine/**`.
- [ ] `git diff --check -- docs/extensions/composition-spine` reports zero
  whitespace errors.
- [ ] The public edge vocabulary (`consumes`, `animates`, `binds-live`,
  `requires`) is frozen in `m0-decisions.md` and is not contradicted by any
  other artifact.
- [ ] Deferred edge names (`materializes`, `produces`, `fallbacks`) appear only
  in deferral/anti-scope prose; no artifact promotes them to public vocabulary.
- [ ] Anti-scope terms appear only as exclusions or deferrals.
- [ ] All fixture matrix rows are sourced from verifiable repo paths; no
  invented literals.
- [ ] Each release example maps to a specific owning milestone (M4, M5, M7b)
  and cites concrete fixture rows and UI surface markers.
- [ ] The JSON-RPC protocol document names exactly four methods (`health`,
  `execute`, `cancel`, `shutdown`), four message types (`progress`, `log`,
  `result`, `error`), eight lifecycle states, and four error classes, and
  states that M0 implements no process manager.
- [ ] All capture profiles beyond the four V1 profiles are marked out-of-V1.
- [ ] No runtime source, SDK export, test, script, config, or UI file is
  modified or created by M0.
- [ ] The Static Command Checklist above passes all items.

## Selector-Preservation Escalation Instruction

If a downstream harness reports empty `test_blast_radius.selectors` despite this
README preserving the seven concrete path selectors above, treat that as a known
selector-preservation limitation of the harness. Do not broaden M0 scope to
include runtime tests or code changes to satisfy a harness metadata gap. M0
artifacts are documentation-only; the harness may not be able to infer test
selectors from markdown files, and that is expected and acceptable.
