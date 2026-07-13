# `north_star_actions` stripping incident: independent architecture and root-cause audit

Date: 2026-07-13 UTC

## Executive verdict

The immediate trigger was a localized allowlist omission, but the incident was **not merely an allowlist bug**. It is a concrete instance of a broader, repeatable failure class: schema-bearing data crossed a worker/capture/normalization/validation/promotion boundary whose contract was manually duplicated, destructively projected before validation, incompletely tested, deployed amid source/schema ambiguity, and retried without early deterministic-failure containment.

The worker consistently supplied the required field. Commit `3ff595994e` deliberately removed all top-level fields outside a handwritten gate allowlist and omitted `north_star_actions`; its new test positively asserted that a malformed value under that legitimate schema key should be stripped. The validator then correctly rejected the already-damaged payload as missing the required field. Fifty-one completed gate attempts repeated that deterministic sequence before the runtime correction and re-drive.

The feature's original Megaplan materials were strong on the semantic gate-to-revise flow but did not establish a producer-to-normalizer-to-validator invariant. The later emergency hardening change did not receive an equivalent schema change-impact review. Newer Workflow Boundary Contracts (WBC) mechanisms describe most of the right controls, but they were not yet landed and enforced on the workflow that was building them. Some older editorial/checklist controls also existed but were either scoped away from this seam, bypassed, or unable to resolve the multi-source runtime state.

Confidence is **high** on the July 13 direct cause, amplification chain, and systemic classification. Confidence is **medium-high** on the precise July 11 historical sequence because that repair occurred across three differing Arnold source trees and some transient runtime evidence was superseded; the durable notes and commit history nevertheless make the schema/runtime-drift contribution clear.

## Evidence examined

- Feature commit `97cc133db6` and initiative `.megaplan/initiatives/megaplan-north-star-sense-checks-revise-design/`, including `NORTHSTAR.md`, briefs, schemas, prompts, handlers, and tests.
- Regression commits `3ff595994e` / parallel `d3bac006c0`, especially `arnold_pipelines/megaplan/model_seam.py` and `tests/arnold_pipelines/megaplan/test_model_seam_recovery.py`.
- Corrective commit `f0cc3e61e5`, including gate contract changes, retry containment, repair identity, watchdog/auditor behavior, and tests.
- The actual incident plan at `/workspace/workflow-boundary-contracts-corrective-20260710/Arnold/.megaplan/plans/s2-contract-foundation-and-20260713-1544/`: `events.ndjson`, `state.json`, gate raw/canonical/carry artifacts, and the retained Hermes gatekeeper SQLite database.
- WBC initiative contracts and rollout notes, particularly `NORTHSTAR.md`, `briefs/m4-boundaryturn-template-promotion-integration.md`, `m6-producer-side-immediate-verification.md`, `m7-phase-coverage-and-full-path-integration.md`, `m8-repair-status-watchdog-auditor-unification.md`, `notes/launch-gates-and-ownership.md`, `notes/2026-07-11-c1-repair-unavailable-root-cause.md`, and `notes/2026-07-11-editable-runtime-verification.md`.
- Current recurrence surfaces in gate, critique, review, finalize, schema, prompt, worker-reconstruction, and scratch-promotion code.
- The originating resident Discord conversation and inbound message records, used only to locate the incident; findings below were independently checked against repository and durable runtime evidence.

## Reconstructed causal chain

1. **Intended contract.** Commit `97cc133db6` added `north_star_actions` to the gate schema, prompt, carry/revise path, and semantic tests. At that commit the capture normalizer was lossless (`dict(payload)`), so the field survived. Ownership was already incomplete: the runtime gate schema and `GateArtifact` contained the field, while `GatePayload` did not. The generated strict schema also made every declared object property required even though the authored `required` list did not initially name this field.
2. **Earlier conflicting symptom and emergency diagnosis.** During the July 11 C1 repair, another runtime/schema combination treated the same top-level field as unsupported for at least 34 attempts. Durable notes recommended normalizing or versioning it consistently. At the time, target checkout, watchdog/resident source, and editable-install mirror were at different revisions. This made deleting the field look like compatibility hardening rather than contract violation.
3. **Regression.** Commit `3ff595994e` changed `_normalize_gate_capture_payload` from lossless copying to a handwritten allowlist that omitted `north_star_actions`. The accompanying test passed a malformed value under that key and asserted that audit succeeded after stripping it. Thus the test encoded the wrong ownership rule: the normalizer, not the schema, decided which schema fields existed.
4. **Worker output.** In the July 13 S2 run, the gate prompt and schema-derived template required the field. Every retained completed Hermes assistant response—from the first failing response through the last—contained `north_star_actions`, usually `[]` and sometimes populated actions. The worker therefore did not omit it.
5. **Loss before validation.** Capture normalization deleted the field. Structural validation ran afterward and reported `missing_required at /north_star_actions`. This ordering destroyed the evidence needed to distinguish producer omission from boundary loss unless raw model output was inspected separately.
6. **Amplification.** `events.ndjson` records 51 completed gate `llm_call_error` events with that same error from July 13, 2026 at 15:55:42 UTC (+00:00) through 17:39:36 UTC (+00:00). The 51 completed gate calls consumed 26,240,759 input and 293,657 output tokens. Failed-phase state accounting nevertheless reported zero cost, reducing operational visibility. Retry logic did not stop on the unchanged deterministic signature.
7. **Repair and recovery.** Commit `f0cc3e61e5` restored the field across the capture allowlist, scratch promotion, prompt example, planning type, runtime required list, and Hermes reconstruction; added parity assertions and field-preservation/retry tests; bounded repeated deterministic phase failures; and stabilized phase-level repair identity. After runtime refresh and one mechanical model re-drive, gate passed on July 13, 2026 at 17:44:41 UTC (+00:00), preserving `north_star_actions: []`; finalize passed at 17:48:26 UTC (+00:00), and execution continued.

## Causal-layer analysis

| Layer | Finding |
|---|---|
| Direct defect | A destructive handwritten gate projection omitted a real schema-owned key before validation. |
| Enabling conditions | The field contract was duplicated across runtime schema, generated schema, planning type, prompt/example, capture allowlist, scratch allowlist, worker recovery defaults, and tests. Generated strictness also differed subtly from the authored `required` list. |
| Amplification | Unchanged deterministic failures launched 51 expensive model calls; failed-phase cost reporting obscured impact; phase-level failures initially lacked robust repair/custody identity. |
| Detection/containment | No raw-candidate-to-normalized-candidate preservation invariant, no immediate producer-side read-back, no effective three-strike circuit breaker at incident start, and no enforced actual-engine/schema provenance gate. Validation occurred only after loss. |
| Planning/editorial/process | The feature plan tested semantic flow but omitted the capture seam. The later hardening patch treated a schema field as unknown compatibility data and its test ratified loss. Existing ownership/runtime launch guidance was not an executable merge/deploy gate. The WBC mechanisms that would have caught this were still being implemented by the affected run. |

## Systemic versus local assessment

This is systemic in mechanism, not universal in outcome. The exact missing gate key is fixed, but the repository still contains structurally similar manual projections and duplicated ownership:

- `_normalize_critique_capture_payload` and its nested critique check/finding/flag normalizers maintain handwritten allowed-key sets.
- Gate, critique, review, and finalize scratch promotion each maintain separate known-key sets, sometimes for legitimate handler-computed fields but without a uniformly enforced ownership declaration.
- Runtime JSON schema, generated strict schema, `TypedDict` planning shape, prompt examples, recovery defaults, and promotion code remain separate representations.
- Runtime introspection can identify the target checkout while execution imports a different engine root; without an explicit engine revision/schema-bundle identity, “current head” is not proof of running-code parity.
- Several validation paths still validate a projected object rather than proving that all schema-owned input fields survived the projection.

These are recurrence surfaces, not claims that each currently loses data. The repeatable failure pattern is: **a new schema property is added to one or several authorities, an older/manual projection silently omits it, validation observes only the projected value, and retries blame the producer.** The July 11 and July 13 opposite treatments of the same key demonstrate that schema-version/source drift can make this pattern recur in both “unexpected extra” and “missing required” forms.

## Planning and evidence mechanisms: what would have prevented or bounded it

- **Original feature Megaplan:** insufficient at this seam. Its closure evidence proved gate/carry/revise semantics and dangerous-action blocking, but not a real worker output through capture normalization and schema validation. A generated all-properties preservation test at `capture_step_output` would have prevented `3ff595994e` from merging.
- **WBC M4 BoundaryTurn/promotion receipt:** if enforced at the capture boundary with raw and promoted hashes/key sets plus schema version, it would have localized the deletion immediately. A receipt containing only post-normalization data would not suffice.
- **WBC M6 immediate producer verification:** a parent read-back and just-completed contract check would have stopped the phase after the first damaged promotion, provided it compares the raw candidate or receipt to the canonical artifact.
- **WBC M7 phase coverage:** a mandatory broken-promotion fixture for every structured phase would have placed gate capture under the common contract rather than relying on semantic downstream tests.
- **WBC M8 unified finding/repair/status identity:** an unchanged finding fingerprint including phase, schema/template version, engine identity, and failure pointer would have routed repair once and prevented repeated repair churn.
- **Launch gates and ownership matrix:** the documented source-to-owner and contract-to-producer matrix, clean unique runtime workspace, and runtime revision parity checks would have exposed the July 11 split-source premise. They were guidance, not a fail-closed executable control on this launch.
- **Corrective three-strike circuit breaker (`f0cc3e61e5`):** would have bounded this incident to three identical failures rather than 51. It contains impact but does not prevent schema loss.

## Assessment of fixes already made

`f0cc3e61e5` is a substantive incident fix, not a cosmetic field addition. It repairs the complete known gate path, adds a gate-schema/allowlist import-time parity assertion, tests empty and populated action preservation through the real capture call, adds repeated-retry stability coverage, introduces a three-identical-failure stop, and makes phase-level repair claims possible without a task ID. Focused verification of the deployed runtime checkout passed 345 tests covering model-seam recovery, automatic blocked recovery, repair custody, meta-repair, progress auditing, and cloud status.

It does not yet make the repository single-authority. The import-time gate assertion still compares one manual constant with one schema projection; it does not derive every normalizer/scratch projection, prove nested preservation, cover all phases, or establish actual runtime/schema provenance. A concurrent technical audit is working on schema-derived gate projection and provenance tests; those uncommitted changes were treated as user work and not altered by this audit.

## Prioritized structural recommendations

1. **P0 — Make projection schema-directed and preservation-testable.** At every model capture boundary, derive schema-owned top-level and nested keys from the exact schema version. Permit explicit handler-owned/computed fields only through a named extension contract. Add a generated invariant: every schema property present in input survives normalization unchanged; unknown extras may be removed. Run it for every structured phase in CI.
2. **P0 — Validate before destructive normalization, then validate after promotion.** Parse and validate the raw candidate against the producer contract before any lossy compatibility transform. Record raw/normalized/canonical hashes, key sets, schema/template version, and loss decisions in the BoundaryReceipt. Any removal of a schema-owned key is an immediate boundary failure.
3. **P0 — Enforce runtime provenance.** Capture and display the actual imported engine root, engine commit/tree state, schema-bundle hash, target commit, prompt/template version, and compatibility declaration. Fail launch or resume when the tuple is unapproved; do not assume target HEAD identifies the executing engine.
4. **P0 — Keep deterministic retry containment fail-closed.** Retain the three-identical-signature breaker. Do not launch another model call unless model binding, code/schema/template identity, or input fingerprint changed. Attribute tokens/cost to failed phases.
5. **P1 — Give phase repair a stable contract identity.** Use a fingerprint over phase, boundary, JSON pointer/error class, input/output hash, schema/template version, and engine identity. Repair custody, status, watchdog, and auditor must consume that same identity and escalate unchanged verified repairs.
6. **P1 — Add an executable schema change-impact gate.** A schema-property diff must enumerate affected producers, prompts/templates, normalizers, promoters, recovery/reconstruction paths, planning types, compatibility policy, and fixtures. Generate the contract-to-producer matrix where possible; block merge on uncovered owners.
7. **P1 — Test the full boundary, not only semantics.** For each structured phase, run a fixture from representative worker response through capture, raw validation, normalization, audit, canonical promotion, receipt emission, and parent read-back. Include current and prior supported schema versions plus one intentionally broken promotion.
8. **P2 — Roll WBC M4/M6/M7/M8 through observe-only to enforcement with support evidence.** A checklist is not a rollout gate. Each phase family should graduate only after receipts, provenance, broken-boundary fixtures, repair identity, and fallback/rollback behavior are demonstrated in the real runtime topology.

## Remaining uncertainty and operational caveat

The retained July 13 evidence proves worker output, boundary loss, retry count, and recovery. The exact July 11 executing code/schema tuple cannot be reconstructed with the same confidence because multiple source trees were active and transient artifacts changed, which is itself part of the failure. The current gate defect is repaired and the affected chain advanced, but broader manual projection and runtime-provenance surfaces remain until the schema-derived and boundary-contract work is merged, deployed, and exercised under fail-closed rollout gates.
