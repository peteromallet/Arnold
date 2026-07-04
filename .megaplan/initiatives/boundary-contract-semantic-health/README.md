# Boundary Contract Semantic Health

This initiative creates one generalized boundary contract system for Megaplan
and future Arnold workflows.

It merges:

- immediate semantic-health repair triggers for the prep/state divergence class;
- BoundaryTurn / structured-output template promotion;
- TransitionWriter / authority-increasing routing validation;
- watchdog, repair-loop, cloud status, and 6h auditor consumption of the same
  findings.

The sequence is deliberately staged. M1 protects the real incident class quickly;
M2/M6 prove immediate repair triggering before the generic model hardens; later
milestones fold that protection into the generalized boundary contract.

## Milestones

| Milestone | Brief | Outcome |
| --- | --- | --- |
| M1 | `briefs/m1-prep-semantic-health-guard.md` | Detect prep artifact/state divergence through watchdog fallback. |
| M2 | `briefs/m2-semantic-finding-custody-and-repair-queue.md` | Store structured findings and enqueue repair safely. |
| M6 | `briefs/m6-producer-side-immediate-verification.md` | Run scoped post-boundary verification and immediate enqueue. |
| M3 | `briefs/m3-boundary-contract-foundation.md` | Define contracts, receipts/evidence, and findings as separate concepts. |
| M4 | `briefs/m4-boundaryturn-template-promotion-integration.md` | Make template/BoundaryTurn promotion emit contract records. |
| M5 | `briefs/m5-transition-writer-authority-integration.md` | Align authority-increasing transitions with contracts. |
| M7 | `briefs/m7-phase-coverage-and-reducer-boundaries.md` | Extend coverage across phases, children, and reducers. |
| M9 | `briefs/m9-chain-pr-cloud-boundaries.md` | Cover chain milestones, PR merge, cloud repair boundaries. |
| M8 | `briefs/m8-repair-loop-status-auditor-consumption.md` | Repair/status/auditor consume shared findings. |
| M10 | `briefs/m10-general-workflow-boundary-conformance.md` | Make new workflow boundaries contract-first by default. |

The numbering preserves the original drafting order. The chain executes M6
before M3 because producer-side verification must prove the repair path before a
shared abstraction can safely generalize it. M9 executes before M8 so custody
contracts exist before status/auditor consumption is required.

## Run Notes

This is a wide, high-risk architecture epic. Use a thorough profile and keep M1
small. The blast radius increases sharply after M3.

Recommended execution:

```bash
python -m arnold_pipelines.megaplan init \
  --project-dir /Users/peteromalley/Documents/Arnold \
  --profile partnered-5 \
  --robustness full \
  ".megaplan/initiatives/boundary-contract-semantic-health/chain.yaml"
```
