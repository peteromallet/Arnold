# Megaplan Native Parity Existing-Work Swarm Synthesis

Generated: 2026-07-09

Source: 48 DeepSeek reports in `.tmp/native-parity-existing-work-swarm/results/`.
The swarm checked each planned component through three lenses where possible:
current code, prior epics, and reusable/generalizable adjacent machinery.

## Executive Verdict

The swarm did not find that the native semantic parity work is already complete.
It found a large amount of reusable scaffolding and several domains where the
behavioral machinery is already substantial, but the central North Star remains
unmet: `workflow.pypeline` and named native subworkflows are still not the sole
source-readable semantic authority.

The most important adjustment is sequencing, not destination. We should reuse the
existing evidence generator, row/conformance YAMLs, runtime substrate, typed
outcomes, execute policies, override matrix, boundary contracts, native goldens,
and installed-wheel smoke tests. We should not accept any of the old conformance
ledgers as closure proof.

## High-Confidence Findings

### 1. S0 North Star Actions and Runner Pinning Are Greenfield

Verdict: adjacent only.

What exists:

- Gate already writes `gate_carry.json` through `handlers/gate.py`.
- Revise already has meta-field extraction and feedback plumbing in
  `orchestration/critique_runtime.py`.
- Runtime schemas for gate/revise exist under `arnold_pipelines/megaplan/schemas/`.
- Runner identity concepts exist nearby in pipeline identity/fingerprint artifacts.

What does not exist:

- No `north_star_actions` field in `gate.json` or `gate_carry.json`.
- No `north_star_actions_addressed` field in `revise.json`.
- No schema-assigned severity for dangerous North Star categories.
- No clean-context auditor/canary path.
- No runner pin scripts.
- No `north_star_critical` chain/milestone field.

Plan adjustment:

- Keep S0 as one aggressive sprint, but structure it as two internal workstreams:
  runner pinning, and gate-to-revise North Star action plumbing.
- Do not split it into multiple calendar sprints unless implementation proves it
  cannot fit. The actual code change rides existing gate/revise plumbing; the
  feature is greenfield, but not a semantic extraction.

### 2. Checker Authority Partly Exists, but the Hard Bar Is Not Built

Verdict: partly exists.

What exists:

- `arnold/workflow/source_compiler.py` already has row-evidence checking and
  strict paths for some S2/S3 rows.
- `tests/arnold/workflow/test_row_evidence_checker.py` exists.
- `arnold/workflow/semantic_evidence.py`, `boundary_contracts.py`, and the old
  conformance YAMLs form a usable starting vocabulary.
- `scripts/generate_native_representation_evidence.py` has reusable declarative
  scan shapes and evidence assembly.

What does not exist:

- `AWF253_PROHIBITED_SEMANTIC_CARRIER`.
- `arnold/workflow/megaplan_semantic_rows.yaml`.
- Package-wide carrier scanner/classifier/reconciler.
- Current-shape negative fixture.
- Renamed/re-encoded structural evasion fixtures.
- Strict installed-package checker mode.

Plan adjustment:

- S1a must stay first and must externalize the row registry before rows expand.
- Reuse `generate_native_representation_evidence.py` and the existing row evidence
  tests, but do not build a parallel evidence stack.
- Build structural carrier detection as shared machinery consumed by both checker
  rules and final conformance generation.

### 3. Evidence Substrate Has Strong Pieces, Not the Required Harness

Verdict: adjacent only.

What exists:

- `arnold/kernel/replay.py` has replay cursor and content-hash validation.
- `arnold/runtime/semantic_replay.py` has structural semantic comparison and event
  journal replay.
- `docs/arnold/megaplan-native-representation-scenarios.yaml` exists locally and
  is a useful split-outcome inventory.
- `tests/arnold_pipelines/megaplan/fixtures/native_goldens/` contains D1-D8 and
  D12 native golden traces.
- `tests/arnold_pipelines/megaplan/test_installed_package_composition_smoke.py`
  already proves important installed-wheel/package-resource behavior.

What does not exist:

- Deterministic replay harness with canned worker payloads.
- Baseline freeze/check scripts.
- Headless control-injection API for destructive approval, tiebreaker choices,
  and other interactive split outcomes.
- Installed-package strict checker path.

Plan adjustment:

- Use route/state/next-command/suspension baselines first; defer artifact-hash
  canonicalization unless artifact content becomes parity proof.
- Build the harness from `semantic_replay.py`, `ReplayCursor`, native goldens, and
  the existing scenarios YAML.

### 4. Native Runtime Substrate Is Better Than Expected

Verdict: partly exists, with a narrower hard gap than earlier audits implied.

What exists:

- Native `parallel_map(items=...)` lowering exists in
  `arnold/pipeline/native/compiler.py`.
- Runtime `items_ref` resolution exists in `arnold/pipeline/native/runtime.py`.
- Parallel-map suspension/reentry exists in the native runtime.
- Generic native suspension/reentry tests exist.

What remains:

- Megaplan-specific substrate tests are missing.
- Manifest backend dispatch still consults components/handler-like route maps.
- `break`/`continue` loop syntax is explicitly rejected by the compiler.

Plan adjustment:

- S1 runtime substrate should be reframed from "prove/build all substrate" to
  "prove native runtime capabilities, then replace Megaplan manifest dispatch."
- Do not implement `break`/`continue` unless S2-S5 truly require language-level
  loop exits. Decision-route loop exits may be sufficient.

### 5. Typed Outcomes and Builder Slice Are Substantially Started

Verdict: partly exists.

What exists:

- Typed outcomes exist for gate, tiebreaker, review, override, and execute policy.
- `workflow.pypeline` already imports and branches on these types in places.
- Some source-derived topology helpers exist.

What remains:

- `build_pipeline()` still reconstructs much from component metadata.
- `handler_ref` and `route_bindings` remain in canonical source and component
  declarations.
- Installed-package parity is not strict-checker parity.

Plan adjustment:

- Make one builder edge source-owned early and prove the old component route
  binding cannot affect behavior.
- Treat this as the bridge between checker infrastructure and later extraction.

### 6. Front-Half Work Has Skeletons, Not Authority

Verdict: partly exists.

What exists:

- `workflow.pypeline:390-470` has the front-half shape.
- `front_half.pypeline` exists as a prior partial extraction target.
- Native goldens include prep/plan, critique, gate preflight, and gate/revise
  substrate traces.

What remains:

- The live workflow still calls `AUTHORING_PREP`, `AUTHORING_PLAN`,
  `AUTHORING_CRITIQUE`, `AUTHORING_GATE`, and `AUTHORING_REVISE` from
  `components.py`.
- Gate/critique/revise behavioral decisions still live in handlers and metadata.

Plan adjustment:

- Split front-half into two extraction sprints: prep/plan/critique first, then
  gate/revise loop. This keeps the coupled gate/revise work intact while avoiding
  an overloaded all-front-half sprint.

### 7. Tiebreaker Is Source-Visible but Still Cosmetic

Verdict: partly exists.

What exists:

- Four tiebreaker phases are visible in `workflow.pypeline`.
- Boundary contracts and fixtures exist.
- Checker shape checks can detect a single-wrapper anti-pattern.

What remains:

- The four phases still route through legacy handler-backed component calls.
- Replan rejoin remains state mutation rather than source authority.
- Old component workflow metadata survives.

Plan adjustment:

- Keep S3 as a full sprint, but focus it on replacing cosmetic source visibility
  with semantic ownership and proving replan rejoin.

### 8. Execute Scheduling Is the Most Reusable Domain

Verdict: substantially exists, needs verify/harden and extraction.

What exists:

- `compute_task_batches`, `schedule_batches`, `split_oversized_batches`, and batch
  complexity are pure and reusable.
- `execute/policy.py` already contains pure typed policy for blocked retry,
  destructive approval, tier routing, and next-step decisions.
- `execute/batch.py` runs dynamic task batches.
- `workflow.pypeline` already has execute `parallel_map` shape.
- Tests exist for tier binding, reducer binding, topology golden, and native
  manifest pieces.

What remains:

- No end-to-end strict proof that `parallel_map(items="megaplan.execute.batches")`
  runs from lowered source through the current Megaplan runtime path.
- Old handler/auto execute routing can still own behavior.
- Dead-delete and frozen baseline tests are missing.

Plan adjustment:

- Reclassify execute DAG scheduling from "build" to "verify, baseline,
  dead-delete, and collapse route authority."
- Split execute into scheduling/fanout and approval/resume to keep approvals,
  blocked retry, and fresh-session behavior reviewable.

### 9. Review and Finalize Have Policy Scaffolding, but S5 False-Passes Today

Verdict: partly exists.

What exists:

- Review fanout/fanin shape is visible in `workflow.pypeline`.
- `ReviewOutcome` and policy surfaces exist.
- Finalize handlers and fallback/baseline logic exist.

What remains:

- S5 checker rows can pass on `Mapping` existence in `REVIEW_POLICY` or
  `FINALIZE_POLICY`, which is the old false-pass pattern.
- Final projection routes still live in component policy metadata rather than
  source-owned constructs.

Plan adjustment:

- Split S5 into review/rework and finalize/terminal projection.
- Allocate a specific negative fixture where policy metadata exists but named
  source constructs are absent.

### 10. Override Surface Is Largely Built, but Split-Brained

Verdict: substantially exists, not semantically complete.

What exists:

- `handlers/override.py` implements all override actions.
- `workflows/override_matrix.py` is a strong declarative authority matrix.
- `planning/control_binding.py` and `arnold/control/interface.py` provide a
  generalizable control-transition abstraction.
- Boundary contracts and authority receipts exist.
- Some auto-driver integration exists.

What remains:

- Handler dispatch is still the production route.
- Control-interface routing is feature-flagged.
- Auto-drive can still act as a second route brain.
- Compatibility and route dispatch projections still need quarantine/fencing.

Plan adjustment:

- Reframe S6a as "collapse/extract existing override surface," not "build
  override surface."
- Use `OVERRIDE_ACTION_MATRIX`, `AuthorityRecord`, and `ControlTransition` as
  templates for other human/control boundaries.

### 11. S7 Tooling Is Not Just Final Assembly

Verdict: adjacent only.

What exists:

- `scripts/generate_native_representation_evidence.py` is a strong evidence
  bundle generator.
- `scripts/validate_native_representation_conformance.py` validates the old
  conformance model.
- Local final-conformance tests and scenarios files exist, though not all swarm
  agents saw them because some are untracked local assets.

What does not exist:

- `check_megaplan_native_semantic_parity.py`.
- Carrier scan/classify/reconcile scripts.
- Exemption ledger checker.
- Baseline freeze checker.
- Scenario-row matrix generator.
- New strict generated conformance report generator.
- Runtime narrowing validator.

Plan adjustment:

- Pull S7 tooling forward. S1a/S1b should create the scanner, row registry,
  strict checker, baseline freeze, and scenario validation scripts. S7 should
  rerun and aggregate them, not invent them at the end.
- Refactor `generate_native_representation_evidence.py` rather than writing a
  parallel evidence generator.

## Existing Assets To Reuse Directly

- `scripts/generate_native_representation_evidence.py`
- `scripts/validate_native_representation_conformance.py`
- `docs/arnold/megaplan-native-representation-scenarios.yaml`
- `docs/arnold/megaplan-native-representation-conformance.yaml`
- `docs/arnold/megaplan-native-representation-traceability.yaml`
- `docs/arnold/proof-map.json`
- `arnold/workflow/semantic_evidence.py`
- `arnold/workflow/source_compiler.py`
- `arnold/workflow/handler_semantics.py`
- `arnold_pipelines/megaplan/workflows/boundary_contracts.py`
- `arnold_pipelines/megaplan/workflows/override_matrix.py`
- `arnold_pipelines/megaplan/workflows/events.py`
- `arnold_pipelines/megaplan/native_interfaces.py`
- `arnold_pipelines/megaplan/outcomes.py`
- `arnold_pipelines/megaplan/execute/policy.py`
- `arnold_pipelines/megaplan/_core/io.py`
- `arnold_pipelines/megaplan/_core/scheduler/topo.py`
- `arnold/control/interface.py`
- `arnold_pipelines/megaplan/planning/control_binding.py`
- `arnold/kernel/replay.py`
- `arnold/runtime/semantic_replay.py`
- `tests/arnold_pipelines/megaplan/fixtures/native_goldens/`
- `tests/arnold_pipelines/megaplan/test_installed_package_composition_smoke.py`
- `tests/arnold/conformance/test_deleted_surfaces.py`
- `tests/arnold/conformance/test_megaplan_coupling_gate.py`

## Assets To Avoid Treating As Proof

- `docs/arnold/megaplan-native-representation-conformance-report.md`
- Old `conformance.yaml` rows that mark source/component existence as implemented.
- `Pipeline.native_program` claims unless the runtime object actually exposes and
  executes that path.
- `workflow.pypeline` existence by itself. It is an authored skeleton until strict
  checker evidence and dead-delete tests prove source authority.
- Component policy `Mapping` existence for S5 rows.
- `override_matrix.py` as final proof; it is a strong source for extraction, not
  the extracted source route authority.
- Handler purity inventories by themselves.
- Installed-wheel smoke tests that do not run the strict checker on installed
  source.

## Recommended Plan Delta

1. Keep the North Star and end-state unchanged.
2. Keep S0 to one aggressive sprint, but explicitly call it greenfield runner and
   gate/revise plumbing over existing carry paths.
3. Split early infrastructure into:
   - checker authority and carrier reconciliation,
   - deterministic evidence/baseline substrate,
   - native runtime/manifest dispatch proof,
   - builder edge slice.
4. Pull S7 tooling forward: build the scanner, row registry, strict checker,
   baseline freeze, and scenario-row matrix before extraction sprints depend on
   them.
5. Reclassify S4 execute scheduling as hardening/extraction, not greenfield build.
6. Reclassify S6 override as collapse/extraction of an existing split-brain
   surface, not greenfield build.
7. Split large extraction phases into aggressive two-week sprints:
   - S2a prep/plan/critique
   - S2b gate/revise
   - S4a execute DAG/scheduling
   - S4b execute approval/resume
   - S5a review/rework
   - S5b finalize/terminal projection
   - S6a override/control
   - S6b auto/manifest/compatibility
8. Use S0 North Star questions as review tripwires, not substitutes for strict
   checker, carrier scan, baseline, and mutation gates.

## Suggested Updated Sprint Spine

This is the lean, evidence-backed spine after absorbing the swarm:

1. S0 - Runner Pinning and North Star Action Plumbing
2. S1a - Checker Authority, Row Registry, Carrier Scan, Current-Shape Rejection
3. S1b - Deterministic Evidence Substrate and Baseline Freeze
4. S1c - Runtime Substrate and Manifest Source Dispatch Proof
5. S1d - Typed Outcomes and First Builder Edge
6. S2a - Prep, Plan, Critique Native Authority
7. S2b - Gate and Revise Native Loop
8. S3 - Tiebreaker and Replan Native Flow
9. S4a - Execute DAG and Scheduling Hardening
10. S4b - Execute Approval, Blocked Retry, Fresh Session, Partial Resume
11. S5a - Review Fanout, Rework, Caps
12. S5b - Finalize Fallback and Terminal Projection
13. S6a - Override and Human Control Surface Collapse
14. S6b - Auto, Manifest Backend, Compatibility Quarantine
15. S7 - Final Generated Conformance and Rollout

This is still roughly 15 aggressive two-week sprints. The swarm bought
confidence and reuse, not a collapse to a few sprints.

## Open Follow-Up Checks

- Confirm whether S2-S5 require language-level `break`/`continue`, or whether
  decision-route loop exits are sufficient.
- Confirm whether route/state/next-command baselines are enough for all planned
  parity gates, avoiding artifact-hash canonicalization until needed.
- Decide whether S7 script consolidation is acceptable. A single
  `reconcile_megaplan_semantic_carriers.py` with subcommands may be cleaner than
  separate scan/classify/reconcile/exemption scripts.
- Decide whether S0 clean-context auditor/canaries are exit-gate required in the
  first implementation sprint or allowed as immediate follow-up. For this epic,
  keeping them in S0 is safer because they are the review substitute.
