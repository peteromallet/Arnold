# Scripts

`scripts/` contains operator scripts for one-off or historical maintenance.
They are intentionally outside the installed package surface.

Current scripts:

- `adopt_plan.py` adopts a finalized plan directory into an existing chain so
  the chain can resume at execute.
- `backfill_step_receipts.py` dry-runs by default and can add provenance-tracked
  backfilled token or cost fields to historical `step_receipt_*.json` files.
- `chain_done_gate.py` blocks chain completion when persisted chain state says a
  milestone is complete but that milestone's plan `state.json` is not `done`,
  completion/backstop modes are non-blocking, or review blockers are still open.
- `m6_purge_gate.py` blocks clean-break completion when shipped product packages
  still contain legacy `_pipeline/` or `stages/` directories, legacy Megaplan
  constructors, or tests that keep those constructors alive.
- `silent_failure_census.py` scans `megaplan/**/*.py` for silent exception
  handlers and direct `stderr` writes, then classifies them for the M3a cleanup
  policy.

Prefer dry-run modes first, and run scripts from the repository root unless a
script's help text says otherwise.

Workflow-manifest-runtime final merge gate:

```bash
python scripts/chain_done_gate.py \
  --spec .megaplan/briefs/workflow-manifest-runtime/chain.yaml \
  --state .megaplan/briefs/workflow-manifest-runtime/.megaplan/plans/.chains/chain-dd4726d3997c.json \
  --blockers .megaplan/briefs/workflow-manifest-runtime/blockers.json

python scripts/m6_purge_gate.py
```
