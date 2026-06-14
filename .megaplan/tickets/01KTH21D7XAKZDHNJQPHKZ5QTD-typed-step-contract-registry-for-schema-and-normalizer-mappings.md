---
id: 01KTH21D7XAKZDHNJQPHKZ5QTD
title: Typed step contract registry for schema and normalizer mappings
status: open
source: human
tags:
- megaplan
- schemas
- contracts
- tech-debt
- reliability
codebase_id: null
created_at: '2026-06-07T12:48:33.022359+00:00'
last_edited_at: '2026-06-07T12:48:33.022359+00:00'
epics: []
---

Problem
Step contracts are duplicated across worker dispatch, capture validation, compatibility modes, required-key extraction, and ad hoc normalizer branches. Drift has already caused blockers: `prep-research` worker units validated against the wrong aggregate schema in some paths, and `prep-distill` needed a one-off null-to-string normalizer.

Acceptance criteria
- Add a single `StepContract`/registry source of truth for step name, schema key, compatibility mode, output kind, and normalizer hooks.
- Derive `STEP_SCHEMA_FILENAMES`, capture schema keys, compatibility modes, and required-key views from that registry.
- Add registry consistency tests proving dispatch schema key equals capture schema key for every step and that all schema keys exist in `SCHEMAS`.
- Move existing per-step normalizers behind registry-attached hooks without changing current behavior.
- Preserve live-chain compatibility during migration by first adding the registry as a checked mirror, then deriving existing dicts from it.

Suggested touchpoints
- `arnold/pipelines/megaplan/schemas/step_registry.py`
- `arnold/pipelines/megaplan/workers/_impl.py`
- `arnold/pipelines/megaplan/model_seam.py`
- `arnold/pipelines/megaplan/schema_seeds.py`
- `tests/arnold/pipelines/megaplan/test_step_registry.py`

