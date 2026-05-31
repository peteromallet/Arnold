# Scripts

`scripts/` contains operator scripts for one-off or historical maintenance.
They are intentionally outside the installed package surface.

Current scripts:

- `adopt_plan.py` adopts a finalized plan directory into an existing chain so
  the chain can resume at execute.
- `backfill_step_receipts.py` dry-runs by default and can add provenance-tracked
  backfilled token or cost fields to historical `step_receipt_*.json` files.

Prefer dry-run modes first, and run scripts from the repository root unless a
script's help text says otherwise.
