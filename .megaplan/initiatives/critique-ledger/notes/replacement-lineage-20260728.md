# Critique-ledger replacement lineage

## Cancelled predecessor

- Session: `critique-ledger-m9-glm-20260723`
- Archive:
  `/workspace/.paused-epics/critique-ledger-m9-glm-20260723/Arnold`
- Completed milestone: CL1 contract and M6 oracle
- Cancelled current milestone: `cl2-wbc-backed-ledger-20260724-0351`
- Final state: blocked during execute
- Cancellation decision: do not resume or replan this run; preserve it as a
  read-only source/audit archive.

The predecessor contains uncommitted CL2 implementation and validation work.
That work may be inventoried and selectively ported only when it satisfies the
new contract. Its existence is not evidence that the amended CL2 requirements
are implemented.

## Replacement

- Branch: `megaplan/critique-ledger-accountability-v2-20260728`
- Workspace: `/workspace/critique-ledger-accountability-v2-20260728/Arnold`
- Session: `critique-ledger-accountability-v2-20260728`
- Base: landed CL1 implementation
- Remaining milestones: CL2–CL5 as four ordered sprints
- Amendment:
  `../decisions/reconciliation-safety-amendment-20260728.md`

The replacement is staged only. No chain, worker, watchdog marker, repair loop,
deployment, or runtime effect is authorized by this setup.
