---
name: megaplan
description: Run the canonical Megaplan planning pipeline from its Arnold plugin home.
---

# Megaplan

Use this pipeline for high-rigor planning workflows that need prep, plan,
critique, gate, revise, finalize, execute, review, and tiebreaker stages.

For epic-sized, migration, public-contract, or otherwise drift-sensitive work,
capture durable end-state intent with a North Star anchor: pass
`--north-star PATH` to `megaplan init` for a standalone plan, or declare
`anchors.north_star` in `chain.yaml` for epics.
