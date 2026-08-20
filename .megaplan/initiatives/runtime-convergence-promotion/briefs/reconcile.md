---
type: brief
slug: reconcile
title: Reconcile
epic: runtime-convergence-promotion
created_at: '2026-08-20T09:08:24.351475+00:00'
---

# Reconcile

## Outcome

Select and publish the epic's engine-source commits that were
not already promoted, as a reviewed PR onto `main`.

## Rubric

This milestone is governed by the per-epic runtime end-state
and megaplan reference architecture docs:

- `docs/megaplan-reference-architecture-20260807.md`
- `docs/per-epic-runtime-end-state-20260809.md`

## Scope

Engine-source changes (`arnold_pipelines/`, `arnold/`) not
covered by promotion evidence.

## Constraints

- Selection is evidence, not narrative: output the chosen
  commit SHAs plus verification evidence.
- A verified no-op still records `reconcile-verification.json`.

## Done Criteria

- Selected commits are cherry-picked onto
  `reconcile/<slug>-<date>` from `main`.
- PR merged, intentionally rejected, or verified no-op.
