# S4: Consumption And General Conformance

> Superseded as an executable milestone by C1-C6. Preserved as historical
> checklist material; see the 2026-07-10 corrective reshape decision.

## Outcome

Repair-loop, cloud status, and the 6h auditor consume the same structured
semantic-health and custody findings. The former opt-in adoption proposal is
superseded: the corrective chain requires ledger/conformance adoption for every
declared supported runtime while leaving genuinely out-of-scope runtimes alone.

This sprint collapses the detailed briefs:

- `m8-repair-loop-status-auditor-consumption.md`
- `m10-general-workflow-boundary-conformance.md`

## Scope

IN:

- Add semantic findings to repair-loop context and initial facts.
- Add repair-loop guidance that diagnoses writer/reconciliation/promotion first,
  preserves state integrity, avoids lifecycle hand-edits as primary repair, and
  does not weaken guards.
- Add cloud status fields for lifecycle state, activity phase,
  semantic-health status, repair state, custody state, and repairable issue.
- Add 6h auditor deterministic gather reasons from semantic-health and custody
  findings, including stale active-step worker, unmanaged live process, repair
  success without custody, and watchdog/status custody disagreement.
- Count findings by session, boundary, phase, kind, and repair domain.
- Add meta-repair trigger for repeated unchanged semantic/custody findings.
- Add the public or semi-public workflow boundary contract and reusable template
  authoring/selection surface.
- Add non-Megaplan conformance tests and docs, dependency-gated on native
  platform readiness where required.
- Preserve all detailed acceptance criteria from the two source briefs as the
  sprint checklist.

OUT:

- Making the auditor decide facts the gather layer can compute.
- Collapsing semantic health into lifecycle status.
- Forcing all existing workflows to migrate in one pass.
- Making every workflow cloud-repairable immediately.

## Locked Decisions

- Status renders derived views but does not become source of truth.
- Auditor gather surfaces suspicious facts deterministically.
- Findings unchanged after 2 consecutive independently verified repair
  attempts escalate automatically to meta-repair.
- Megaplan-specific details stay in Megaplan adapters.
- Domain-specific concepts belong in adapters that map onto generic primitives.
- Reusable templates are selectable profiles over the core contract model;
  supported-runtime ledgering and boundary conformance are not optional.

## Done Criteria

1. Repair-loop can repair a semantic finding without `latest_failure`.
2. Cloud status displays semantic health separately from activity and custody
   separately from process liveness.
3. 6h auditor report includes explicit semantic and custody finding reasons.
4. Meta-repair triggers on repeated unchanged semantic/custody findings.
5. Tests cover status separation, custody warning rendering, and auditor gather
   regression.
6. A non-Megaplan graph-shaped workflow defines boundary contracts and gets
   semantic verification, when prerequisite native-platform substrate exists.
7. Docs explain how to add boundaries and how to select, extend, and version
   reusable templates.
8. Conformance tests fail when a new boundary writes artifacts without declared
   durable effects, emits a template instance missing required fields, expects
   an incompatible template version, or uses native-platform-only metadata
   instead of a shared boundary contract profile.
9. Existing Megaplan contracts remain valid through the generic surface.
10. Adapters can express physical/external evidence and partial acceptance
    without changing core schema.

## Touchpoints

- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
- `arnold_pipelines/megaplan/cloud/six_hour_auditor.py`
- `arnold_pipelines/megaplan/cloud/cli.py`
- Arnold workflow/runtime contract modules
- workflow conformance tests
- Megaplan boundary-contract adapter
- docs
