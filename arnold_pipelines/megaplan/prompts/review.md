# M11 Review Prompt Contract (review.md)

## Schema Hash

`REVIEW_SCHEMA_HASH`: `sha256:01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a`

This hash covers the review output contract shape defined below. Any generated
`review.json` whose schema does not match this hash MUST be rejected before
routing.

## Review Outcome Contract

Every generated `review.json` MUST carry:

- `review_verdict`: exactly `"approved"` or `"needs_rework"` (never empty, never a
  third value)
- `review_completion_status`: exactly `"complete"` or `"incomplete"`
- `review_schema_hash`: the SHA-256 above, proving the output conforms to this
  contract version

## Task ID Routing Rules

### FORBIDDEN: Generic Runnable REVIEW IDs

The following patterns MUST NOT appear as `task_id` values in any
`rework_items[].task_id` or `task_verdicts[].task_id` field:

- `REVIEW-{anything}` — synthetic review check IDs are NOT runnable task targets
- `REVIEW` (bare, no hyphen suffix) — insufficient to route to a real task

These are telemetry/blocker-compatibility markers for the executor. They are
NEVER routed to execute as runnable finalize task IDs.

### REQUIRED: Typed Target Routing

Every `rework_items` entry that requires re-execution MUST use the `target`
field with one of:

```json
{"kind": "task", "task_id": "T6"}
{"kind": "bulk", "id": "bulk-1", "task_ids": ["T6", "T7"]}
{"kind": "manifest", "id": "manifest-path-or-ref", "task_ids": ["T6"]}
```

The legacy `task_id` field is backward-compatibility ONLY. It may mirror the
single task target, or be `"REVIEW"` only for review blockers with NO
routable finalize target. A bare `"REVIEW-001"` `task_id` is NEVER acceptable.

### Review Outcome Markers

When the review finds a blocking issue, the `rework_items` entry MUST include
a `deterministic_check`:

```json
{
  "deterministic_check": {
    "command": "<exact shell command that failed>",
    "baseline_status": "failed",
    "post_status": "failed"
  }
}
```

Without this, `review_verdict` MUST be `"approved"`. Prose-only concerns are
advisory and recorded in `issues`, not `rework_items`.

## Sense Check Verdicts

Each `sense_check_verdicts[].verdict` MUST be one of:
- `"Confirmed. <evidence>"`
- `"Waived. <explanation>"`
- `"Blocked. <reason>"`

Never emit a generic, non-deterministic verdict without evidence anchoring.

## Pre-Check Flags

Copy the `pre_check_flags` list verbatim from the prompt into the output.
Do not modify, reorder, or filter any pre-check flag entries.
