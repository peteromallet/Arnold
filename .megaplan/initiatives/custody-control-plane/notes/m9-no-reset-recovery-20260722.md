# M9 no-reset recovery evidence — 2026-07-22

All timestamps in this note are UTC. This recovery reuses the existing
`custody-control-plane` initiative and preserves the launch checkout and every
earlier M9 branch/worktree.

## Preserved launch boundary

- Launch target: `refs/heads/megaplan/custody-control-plane/m8a-planner-compiler-and-executor-efficiency`
- Launch/implementation base: `df02cefe31533e35855e8425bb433058898085ca`
- Launch checkout: `/workspace/custody-control-plane-20260714/Arnold`
- Launch dirty paths were left untouched:
  - `.megaplan/incident-ledger/.events.seq` — SHA-256 `2618182c3894875e16eeafa6c24e1fe926150ebc6403980c2cb1bbff192d296d`
  - `.megaplan/incident-ledger/events.jsonl` — SHA-256 `74dd59364113beb1581a7d8629206487b7ffa525275b268a6be21`
  - `.megaplan/cloud-logs/m9-rebuildable-projections-20260722-0431.log` — SHA-256 `af0104720a962234b531bbf94ece62ac2bbb5c2aeaa9e97ee33d5ce9df2d28fd`
- Aggregate tracked dirty diff fingerprint: SHA-256 `4499a73a8356e34bc653241e398faf6ecee8510f118bc7aed05e87fb1ed22ccc`.
- Aggregate untracked-name fingerprint: SHA-256 `b9d178e261ef2b2bc3ba8298c6893d867def2cbd5828fd6318c495920d775713`.
- Isolated recovery worktree: `/workspace/.megaplan/worktrees/custody-m9-no-reset-20260722t0945z`
- Isolated recovery branch: `refs/heads/repair/custody-m9-no-reset-20260722t0945z`

## Lineage and carry-forward disposition

- Candidate landed baseline `86c1de74ce8fdeae48750c2f4c0555e82fc9cf87`
  and target `df02cefe31533e35855e8425bb433058898085ca` are siblings from
  `9c99688b67a7c6c7fa37d4b622b68643e787d94c`; neither is an ancestor of
  the other. The candidate is reference evidence, not a replay base.
- Preserved earlier M9 tip `e041ae04c30823064f945b2ed963d1a06195ec25`
  diverges from the target at merge base
  `7e09e33ed6acb187aa43158224bb08b5bbf2d215`. It is not replayed wholesale.
- Ledger path: the earlier M9 `arnold/workflow/ledger_migrations.py` differs by
  1,416 lines from the target. Retained only as reference; the current M6A/M8A
  target implementation and tests remain authoritative.
- Query path: earlier M9 adds a 955-line `arnold/workflow/wbc_queries.py` while
  candidate `86c1de74…` and reconciled M8 branch `a91daefe…` carry independently
  reviewed variants. No query implementation is cherry-picked before the fresh
  M9 plan revalidates current prerequisites.
- Projection path: earlier M9 adds
  `arnold_pipelines/megaplan/observability/projection_rebuild.py` and changes
  `custody/projections.py`; these remain reference inputs for fresh selective
  implementation and testing.
- Repair path: the one-line `custody/repair_receipt.py` divergence and the much
  larger work-ledger divergence are not replayed. Current fail-closed repair
  adoption at `df02cefe…` is preserved.

## Deterministic blocker and prerequisite truth

The current plan `m9-rebuildable-projections-20260722-0431` reached critique
iteration 2 and a `PROCEED` gate, then finalize failed three times. Raw provider
evidence in `finalize_v2_raw.txt` records HTTP 400 `invalid_json_schema` because
`properties.critique_resolution_coverage` was an array without `items` in the
pinned resident runtime revision
`7a5f9d39c52db851a63bfc3f36619df792e1688c`. This is a runtime/workflow defect,
not a product-data or human-approval block.

The target already contains source fix `b6d0aee5e44ae398bd847479ddb6531b733d0c1a`
(`Fix finalize response array schema`) and its recursive Codex schema regression.
This recovery adds a direct equality regression between the model-owned finalize
contract and the runtime capture schema so the typed critique-resolution rows
cannot silently diverge again.

Product/data prerequisites remain fail-closed:

- `evidence/wbc-boundary-inventory-validation.json` reports `passes: false`,
  `prerequisite_status: UNKNOWN`, with 15 declared contracts lacking matrix rows.
- `evidence/m8a-f01-f17-executor-wiring.json` marks all 17 findings
  `evidence-only`; it expressly grants no action authority.
- `evidence/m6a-prerequisite-resolution.json` explains and resolves historical
  blockers 003/004, but `evidence/ownership-decision-record.json` still contains
  four stale blocked rows. The stale record is not rewritten or treated as
  acceptance evidence during this recovery.

The revised M9 plan handles these conditions by emitting per-class unavailable
coverage, unknown denominators, non-authoritative consumer rows, raw-fallback
status, compatibility deadlines, and negative-authority tests. It defers
absolute joined-total and blanket zero-reader claims. No missing evidence is
fabricated and positive action authority remains disabled/fail-closed.

## Recovery result

Pending execution and post-recovery re-read.
