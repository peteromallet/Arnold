# Megaplan Native Representation Current State

## Current Decision

The final native-representation conformance check should be a validation stage
inside the final sprint/milestone lifecycle:

```text
execute -> validate -> close
```

The final conformance gate belongs in `validate`.

It should not be:

- a Megaplan product workflow step like `execute`, `finalize`, or `review`;
- a separate M7 milestone by default;
- only prose buried inside the final execution brief.

## What The Validation Stage Should Do

The validation stage should run after the final sprint execution has produced
its evidence and before the sprint/epic can close.

It should:

1. Load the target report and traceability contract:
   - `docs/arnold/megaplan-native-representation-report.md`
   - `docs/arnold/megaplan-native-representation-traceability.yaml`
2. Read prior chain evidence, proof maps, completion manifests, and final
   sprint artifacts.
3. Require or inspect:
   - `docs/arnold/megaplan-native-representation-conformance-report.md`
   - `docs/arnold/megaplan-native-representation-conformance.yaml`
4. Verify every traceability row is accounted for as `implemented` or explicit
   `deferred`.
5. Verify implemented rows use valid semantic carriers:
   - `canonical_source`
   - `declared_policy`
   - `audited_pure_phase_body`
6. Verify `proof_categories` cover the proof labels required by the matching
   traceability row.
7. Verify proof artifact paths and carrier evidence paths exist.
8. Verify deferred rows include owner, reason, and blocking proof.
9. Run:

   ```bash
   python scripts/validate_native_representation_conformance.py \
     --conformance docs/arnold/megaplan-native-representation-conformance.yaml
   ```

10. Fail closed if validation fails. Closing the sprint/epic should only be
    allowed after validation passes.

## What To Keep

Keep the hardening already committed:

- `docs/arnold/megaplan-native-representation-traceability.yaml`
- `scripts/validate_native_representation_conformance.py`
- final conformance report/ledger concept
- semantic carrier requirements
- proof category requirements
- tests around the validator and alignment artifacts

Recent relevant commits:

- `c90c9eb1 Derive conformance target from traceability`
- `ea625a38 Require final conformance proof categories`
- `1dd8cc6a Read conformance row fields from traceability`

## What To Change Next

The next design/implementation step is to represent the final conformance gate
as structured stage configuration on the final milestone, conceptually:

```yaml
milestones:
  - label: m6-platform-docs-conformance-and-rollout
    idea: .megaplan/initiatives/native-platform-followup/briefs/m6-platform-docs-conformance-and-rollout.md
    stages:
      execute:
        kind: milestone_execution
      validate:
        - kind: final_conformance_gate
          target_report: docs/arnold/megaplan-native-representation-report.md
          traceability: docs/arnold/megaplan-native-representation-traceability.yaml
          conformance_report: docs/arnold/megaplan-native-representation-conformance-report.md
          conformance_ledger: docs/arnold/megaplan-native-representation-conformance.yaml
          validator: scripts/validate_native_representation_conformance.py
      close:
        kind: chain_completion_manifest
```

The exact schema should follow existing chain/harness conventions once the
implementation surface is inspected.

## What To Avoid Or Delete

Do not add a fake M7 milestone just for closeout.

If any uncommitted M7 experiment exists, remove it before continuing. The
desired design is a validation stage inside the final milestone, not a new
milestone.

Avoid duplicating the full final conformance contract in both the final sprint
brief and structured config. The structured validation stage should become the
canonical definition. The brief should only say that execution must produce the
evidence consumed by the validation stage.

## What I Was Doing Toward The Overall Goal

The overall goal was to make the three planned Megaplan epics highly likely to
reach the target in:

`docs/arnold/megaplan-native-representation-report.md`

The work so far has been plan hardening, not execution of the implementation
chains. Specifically, I was:

- anchoring the end state around the native-representation report;
- making the traceability matrix machine-readable and test-covered;
- ensuring the follow-up chains cannot launch out of order;
- adding a final conformance contract so the last epic cannot claim completion
  with weak evidence;
- strengthening the validator so it derives schema, status, semantic carrier,
  proof category, suffix, and required-field rules from traceability metadata;
- using Codex high-reasoning subagents for judgment calls around final
  conformance and proof-category sufficiency.

Important current status:

- The first chain verify has passed from committed sources.
- The composition and platform chain verifies intentionally fail closed until
  the completion chain state/manifest exists.
- The actual three implementation chains have not been run.
- The persistent goal should not be marked complete until the chains run and
  final conformance is proven by current evidence.
