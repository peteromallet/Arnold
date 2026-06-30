# Megaplan Native Representation Review Execution

This file records the first execution pass of the review waves required by
`docs/arnold/megaplan-native-representation-alignment-plan.md`.

## Inputs

- Target: `docs/arnold/megaplan-native-representation-report.md`
- Plan: `docs/arnold/megaplan-native-representation-alignment-plan.md`
- Initiative plans:
  - `.megaplan/initiatives/native-python-pipelines-completion/`
  - `.megaplan/initiatives/native-composition-followup/`
  - `.megaplan/initiatives/native-platform-followup/`
- Current-source reality checked by reviewers:
  - canonical facade: `arnold_pipelines/megaplan/pipeline.py`
  - live workflow source: `arnold_pipelines/megaplan/workflows/workflow.py`
  - workflow builder: `arnold_pipelines/megaplan/workflows/planning.py`
  - handler-ref surface: `arnold_pipelines/megaplan/workflows/components.py`
  - product handlers under `arnold_pipelines/megaplan/handlers/`
  - native compiler/runtime under `arnold/pipeline/native/`

## Reviewer Runs

- High abstraction H0-H9: GPT-5.5 Codex, `model_reasoning_effort=high`,
  read-only.
- Detail D1-D8: GPT-5.5 Codex, `model_reasoning_effort=high`, read-only.
- Detail D9-D15: GPT-5.5 Codex, `model_reasoning_effort=high`, read-only.

## Verdict Summary

No review wave returned `BLOCK`.

The high-abstraction reviewer returned `PASS` for H4, H5, and H8, and
`PASS WITH EDIT` for H0, H1, H2, H3, H6, H7, and H9. The edits were applied:

- make source-path reconciliation a launch gate before composition M1 because
  the current live source is under `arnold_pipelines/megaplan/workflows/`;
- require composition M1/M6 to refuse closure if report-owned stages remain
  single handler-backed stages;
- mark temporary Megaplan-only compiler/runtime paths as `BLOCKING` unless
  M2/M3 generalize or delete them before affected rows become implemented;
- rerun generic coupling and semantic-vocabulary scans in composition/platform
  conformance;
- require a per-row semantics carrier table;
- sharpen native-language gates for runtime-list fanout, typed loop exits,
  policy-call metadata, and nested workflow invocation;
- require platform M6 to rerun the exact composition M6 conformance suite
  against the installed package artifact.

The D1-D8 reviewer returned `PASS` for D2, D3, D4, and D7, and `PASS WITH
EDIT` for D1, D5, D6, and D8. The edits were applied:

- D1 prep/plan golden for blocking questions, resume-clarify, no pre-resume
  plan artifact acceptance, and imported criteria in declared plan outputs;
- D5 tiebreaker `replan` golden and static topology route;
- D6 finalize fixtures for task generation, scoped/full baseline selection,
  missing scoped baseline fallback, user actions, and synthetic before-execute
  gate;
- D8 execute-gate scenarios for approve, deny, cancel, resume, no-review,
  deferred-human, and protected action approval.

The D9-D15 reviewer returned `PASS` for D12 and D15, and `PASS WITH EDIT` for
D9, D10, D11, D13, and D14. The edits were applied:

- D9 review fanout topology for selected checks, reducer/fan-in, ordering, and
  infra retry;
- D10 review cap scenarios and mutation test for moving cap logic into a
  retained handler;
- D11 override matrix generated from current `_OVERRIDE_ACTIONS`;
- D13 rendered policy view for timeout, retryability, escalation, phase model,
  and task-complexity model routes;
- D14 compiler/authoring fixtures for runtime-list `parallel_map`, typed loop
  exits, declared policy calls, nested workflow invocation, and rejection of
  Megaplan-only helpers.

## Current Status

The review waves now agree that the three-epic sequence is structurally aligned
with the target report at planning time. The remaining risk is execution
discipline: M6 conformance in composition and platform must be hard blocking
and must run against the installed package/source that users actually execute.

## Doctrine Revalidation Pass - 2026-06-30

After adding doctrine precedence to
`docs/arnold/megaplan-native-representation-alignment-plan.md`, GPT-5.5 Codex
high-reasoning read-only reviewers reran the three blocking doctrine gates:

- H1 End-State Fit: `PASS WITH EDIT`.
- H7 Native Language Sufficiency: `PASS WITH EDIT`.
- H8 Completion-vs-Conformance Review: `PASS WITH EDIT`.

No blocking reviewer returned `BLOCK`, but all three required edits before the
pre-launch audit can be treated as current. The edits were applied:

- closed the deferral escape hatch so report-owned Megaplan semantics cannot be
  deferred merely because they remain inside handlers, metadata constants, route
  labels, rendered manifests, native traces, or `native_program` shells;
- added a required V2 Python-shaped authoring-contract deliverable covering
  nested workflow invocation, runtime-list maps, typed loop outcomes, declared
  policy-call metadata, stable path identity, and wrapper rejection;
- clarified that static topology for runtime-list fanout shows a typed map/DAG
  template, while runtime tree traces expand concrete selected children;
- required policy conformance to prove policy objects are attached to the
  compiled/rendered workflow, not merely exported as module constants;
- qualified stale or future-looking path references such as
  `arnold/pipelines/...`, `native_runner.py`, and `native_hooks.py` behind
  source-path reconciliation before implementation starts;
- marked completion M7 source-readability proof as substrate only unless
  composition M6 structural conformance, handler-purity, mutation, rendered
  policy, and source-authority gates pass.

The live-source caveat remains: current Megaplan source is still partly
handler-backed (`workflows/workflow.py` calls components whose metadata carries
`handler_ref`, and `workflows/planning.py` still canonicalizes routes/policies).
That is acceptable only as current-state evidence; it is not report conformance.

## Doctrine Sweep Continuation - 2026-06-30

A follow-up GPT-5.5 Codex high-reasoning reviewer reran the remaining
high-abstraction gates against the updated doctrine and current source:

- H0 Matrix Closure Gate: `PASS WITH EDIT`.
- H2 Epic Wiring Audit: `PASS WITH EDIT`.
- H3 Current-State Code Map: `PASS`.
- H4 Source-Authority Audit: `PASS`.
- H5 Manifest Contract Review: `PASS`.
- H6 Runtime/Resume Risk Review: `PASS WITH EDIT`.
- H9 Platform Preservation Review: `PASS`.

The edits were applied:

- updated the target report current-state map so authority is no longer
  described as `planning.py` alone; current source authority is split across
  `workflows/workflow.py`, `workflows/planning.py`, `workflows/components.py`,
  and the public `pipeline.py` facade;
- made completion-vs-composition closure explicit: completion M7 source
  readability is substrate proof, while final report conformance waits on
  composition M6 structural conformance, handler-purity inventory, mutation
  tests, rendered policy view, and source-authority proof;
- tightened deferral language in composition and platform M6 so report-owned
  semantics cannot be hidden in handlers, metadata constants, route labels,
  manifest projection, native traces, or `native_program` shells;
- added source-path reconciliation requirements for stale or future-looking
  paths including `arnold/pipelines/...`, `native_runner.py`, and
  `native_hooks.py`.

Codex separately adjudicated the hard launch-gating question and recommended a
code-backed chain feature rather than a documentation-only checklist. That
feature is now implemented as top-level `launch_preconditions` in chain specs:
`exists`, `contains_text`, and `chain_completed` checks are parsed in
`arnold_pipelines/megaplan/chain/spec.py`, enforced by `validate_paths()`, and
called by both `megaplan chain start` and `megaplan chain verify`.

The follow-up chain specs now declare those gates. Composition is intentionally
blocked until the native-python-pipelines-completion chain state proves every
current milestone `done` against the current completion chain spec hash, with
plan names and merged PR evidence for the review-merge completion chain.
Platform is intentionally blocked until both completion and composition chain
states prove `done` with the same evidence checks, and until composition M6 produces
`docs/arnold/megaplan-composition-conformance-report.md`. Verify failures before
those prerequisites exist are the expected no-launch result.

GPT-5.5 Codex high-reasoning release-gate review on 2026-07-01 then found the
first `chain_completed` version too weak because label/hash-only state could be
forged or stale relative to plan/PR evidence. The gate was tightened to reject
unsupported nested failure-policy keys and require prerequisite chains to have
no active plan, to have advanced past all milestones, and to carry `done`
records with plan names plus merged PR evidence for `merge_policy: review`.
Remaining pre-launch hardening recommendations were machine-readable
traceability rows, a fixed D1-D15 scenario manifest, and artifact/brief hashes
or an authoritative completion manifest.

The first two recommendations were implemented as
`docs/arnold/megaplan-native-representation-traceability.yaml` and
`docs/arnold/megaplan-native-representation-scenarios.yaml`, with focused
pytest validation in
`tests/arnold_pipelines/megaplan/test_native_representation_alignment_artifacts.py`.
The remaining release-hardening question was later adjudicated as mandatory:
dependent chains use `require_manifest: true`, and the harness now supports a
content-addressed `completion-manifest.json` generated by
`megaplan chain manifest --spec ... --proof-map ...`.

GPT-5.5 Codex high-reasoning launch-readiness review on 2026-07-01 found no
additional artifact/test edits needed for this phase. It judged the
traceability/scenario artifacts sufficient for planning readiness and for
launching only `native-python-pipelines-completion`; after the later
release-gate adjudication, completion M7 must produce the authoritative
completion manifest before composition can launch.

After that adjudication, the launch precondition surface was tightened further
with `git_tracked`: all three chains now require their initiative source
directory and load-bearing native-representation docs to be committed in
`HEAD` and clean. This makes the current checkout intentionally no-launch until
those files are committed cleanly, preventing `driver.require_clean_base` from
stashing away staged, modified, deleted, or untracked source before
`megaplan init`.

## Doctrine-Aware Detail Revalidation - 2026-06-30

GPT-5.5 Codex high-reasoning read-only reviewers reran D1-D15 against the
updated doctrine, current source, and current milestone briefs:

- D1 Prep/Plan: `PASS`.
- D2 Critique: `PASS`.
- D3 Gate Preflight: `PASS WITH EDIT`.
- D4 Gate/Revise: `PASS WITH EDIT`.
- D5 Tiebreaker: `PASS`.
- D6 Finalize: `PASS WITH EDIT`.
- D7 Execute DAG: `PASS`.
- D8 Execute Gates: `PASS`.
- D9 Review Fanout: `PASS`.
- D10 Review Caps: `PASS WITH EDIT`.
- D11 Human/Control: `PASS`.
- D12 Runtime/Trace: `PASS`.
- D13 Policy/Platform: `PASS`.
- D14 Compiler/Authoring: `PASS`.
- D15 Handler Extraction: `PASS`.

No detail reviewer returned `BLOCK`. The required edits were applied:

- M6 composition conformance now names gate malformed/empty payload
  normalization, unavailable-agent preflight, high-complexity downgrade,
  flag-resolution fallback, cap/no-progress/severity termination,
  critical-blocker block/escalate, cosmetic-only force-proceed/debt, finalize
  fallback-to-revise, finalize failure, and the synthetic before-execute gate in
  the fixed D1-D15 scenario manifest;
- M1 and M6 now require cap-exhausted review blockers to escalate through a
  declared recoverable-block/control route rather than hiding inside retained
  review-handler `STATE_BLOCKED`, `resume_cursor`, `current_state`, or
  `next_step` mutation.

This revalidation is still a planning/gate sufficiency result, not
implementation conformance. Current source remains handler-heavy; the briefs
must make that debt impossible to close as report conformance unless the
semantics move into canonical source, declared policy, or audited pure phase
bodies with the required structural and mutation proof.
