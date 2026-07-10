# North Star: Messaging Boundary Cleanup V2

The VibeComfy agent panel must have a structural boundary between user-facing
conversation data and internal execution/audit data. Normal chat and detail
render paths should be unable to display raw execution internals by accident.

## End State

- Normal UI renders only safe `TranscriptMessage` and `ResponseDetail`
  projections.
- Internal `ExecutionEvent` data remains available for progress, diagnostics,
  audit, and explicit debug/download surfaces, but is not renderer input.
- Rehydrate/session payloads are projected before browser consumption; frontend
  filtering is a second line of defense, not the primary safety boundary.
- Any compatibility mirror is explicit, tested, documented, and has a deletion
  trigger.
- Sentinel tests prove collapsed chat, expanded details, history/rehydrate, and
  default browser surfaces cannot leak raw execution/debug/audit/provider/path
  fields.

## Non-Negotiables

- Do not broaden this epic into general frontend decomposition.
- Do not change model/provider routing.
- Do not remove audit/debug evidence; isolate it behind explicit affordances.
- Do not reuse old generated plan state or old worktrees as execution base.
- Do not weaken profile model selections while completing the chain.

## Parallel Boundary

This epic owns transcript/detail/event safety. The pristine architecture
follow-up owns non-message architecture hardening: backend contract guardrails,
status/composer/candidate ownership, docs, artifact hygiene, and compatibility
ledger policy.
