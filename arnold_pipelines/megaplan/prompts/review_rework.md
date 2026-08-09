# M11 Review Rework Prompt Contract (review_rework.md)

## Schema Hash

`REVIEW_REWORK_SCHEMA_HASH`: `sha256:0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b`

This hash covers the rework-specific contract below. Any generated rework output
whose schema does not match this hash MUST be rejected before routing.

## Rework Outcome Contract

Every generated rework response MUST carry:

- `rework_verdict`: exactly `"rework_complete"` or `"rework_incomplete"`
  (never a third value, never empty)
- `rework_schema_hash`: the SHA-256 above, proving the output conforms to this
  contract version
- `rework_items_resolved`: list of rework item IDs that were addressed
- `rework_items_unresolved`: list of rework item IDs that remain

## Rework Task ID Routing (Same as review.md)

### FORBIDDEN: Generic Runnable REVIEW IDs

The following patterns MUST NOT appear as `task_id` values:

- `REVIEW-{anything}` — synthetic review check IDs
- `REVIEW` (bare) — insufficient routing

### REQUIRED: Typed Target Routing

Every rework directive that requires re-execution MUST use:

```json
{"kind": "task", "task_id": "T6"}
```

The legacy `task_id` field is backward-compatibility only. A bare
`"REVIEW-001"` `task_id` is NEVER acceptable.

## Deterministic Rework Evidence

Every resolved rework item MUST cite the exact command that now passes:

```json
{
  "resolved_item": "R1",
  "deterministic_check": {
    "command": "<exact shell command that now passes>",
    "previous_status": "failed",
    "current_status": "passed"
  }
}
```

Rework that is claimed resolved without a deterministic check MUST be treated
as unresolved. The executor will re-run the review cycle.

## Pre-Check Flags

Copy the `pre_check_flags` list verbatim from the prompt into the output.
Do not modify, reorder, or filter any pre-check flag entries.
