# Workflow Boundary Contracts

This initiative creates one generalized boundary contract system for Megaplan
and future Arnold workflows.

It merges:

- immediate semantic-health repair triggers for the prep/state divergence class;
- BoundaryTurn / structured-output template promotion;
- TransitionWriter / authority-increasing routing validation;
- watchdog, repair-loop, cloud status, and 6h auditor consumption of the same
  findings.

The sequence is deliberately staged as busy roughly two-week sprint milestones.
The older detailed `m*.md` briefs remain as source/checklist material inside
each sprint, not as top-level cloud milestones.

## Milestones

| Milestone | Brief | Outcome |
| --- | --- | --- |
| S1 | `briefs/s1-operational-semantic-health.md` | Detect semantic progress failures, write durable findings, and enqueue repair. |
| S2 | `briefs/s2-contract-foundation-and-authority.md` | Build the contract/evidence/finding model, reusable templates, BoundaryTurn promotion, and authority records. |
| S3 | `briefs/s3-megaplan-boundary-coverage-and-cloud-custody.md` | Extend contracts across Megaplan phases, reducers, chain/PR transitions, repair records, and cloud custody. |
| S4 | `briefs/s4-consumption-and-general-conformance.md` | Make repair/status/auditor consume findings and add opt-in general workflow conformance. |

Detailed source briefs:

- S1 preserves `m1-prep-semantic-health-guard.md`,
  `m2-semantic-finding-custody-and-repair-queue.md`, and
  `m6-producer-side-immediate-verification.md`.
- S2 preserves `m3-boundary-contract-foundation.md`,
  `m4-boundaryturn-template-promotion-integration.md`, and
  `m5-transition-writer-authority-integration.md`.
- S3 preserves `m7-phase-coverage-and-reducer-boundaries.md` and
  `m9-chain-pr-cloud-boundaries.md`.
- S4 preserves `m8-repair-loop-status-auditor-consumption.md` and
  `m10-general-workflow-boundary-conformance.md`.

## Run Notes

This is a wide, high-risk architecture epic. Every sprint uses
`profile: partnered-5` in `chain.yaml`. Keep S1 focused on live cloud repair
protection; the blast radius increases sharply after S2.

Recommended execution:

```bash
python -m arnold_pipelines.megaplan chain start \
  --project-dir /Users/peteromalley/Documents/Arnold \
  --spec ".megaplan/initiatives/workflow-boundary-contracts/chain.yaml"
```
