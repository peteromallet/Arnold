---
id: 01KTH21CPT1NG0NS16JWC7T7X3
title: Auto-heal runtime schema materialization on plan resume
status: open
source: human
tags:
- bug
- megaplan
- schemas
- runtime
- reliability
codebase_id: null
created_at: '2026-06-07T12:48:32.474176+00:00'
last_edited_at: '2026-06-07T12:48:32.474176+00:00'
epics: []
---

Problem
Runtime schemas are defined in Python (`SCHEMAS`), but workers read schema files from `.megaplan/schemas`. Existing plans do not automatically receive newly added schema files, so live workers can fail even when the code registry is correct. Recent example: `prep_research_finding.json` had to be materialized manually for an in-flight chain.

Acceptance criteria
- Phase entry or plan resume runs a cheap schema health check that re-materializes missing or stale `.megaplan/schemas/*.json` from the canonical Python schema registry.
- Filesystem schemas are treated as a cache/materialization, not the source of truth.
- A test reproduces an existing plan missing a newly added schema and proves the next phase start repairs it before worker dispatch.
- CI/test coverage asserts `ensure_runtime_layout` emits the expected schema file set from `SCHEMAS`.
- Manual edits to generated runtime schema files are overwritten or warned about clearly.

Suggested touchpoints
- `arnold/pipelines/megaplan/_core/io.py`
- `arnold/pipelines/megaplan/schemas/runtime.py`
- `arnold/pipelines/megaplan/workers/_impl.py`
- `arnold/pipelines/megaplan/model_seam.py`
- `tests/arnold/pipelines/megaplan/test_schema_seeds.py`

