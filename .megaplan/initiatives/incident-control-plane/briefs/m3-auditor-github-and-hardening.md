---
superseded_by: custody-control-plane
---

# M3: Auditor, GitHub Sync, And Hardening

## Outcome

The six-hour auditor, recurrence tracking, GitHub/editable-install publication, and cloud rollout use the incident ledger as their source of truth. The system makes persistent recovery failures obvious and durable without leaking secrets or bloating git.

## Design Inputs

- M1 ledger helper and `brief`.
- M2 repairer integration.
- `.megaplan/audits/incident-control-plane-plan-20260703.md`
- `.megaplan/audits/incident-control-plane-codex-review-20260703.md`

## Scope

In:

- Patch the six-hour auditor prompt/wrapper to start from incident ledger state and audit project progress, immediate repair, meta repair, install sync, GitHub sync, live processes, stale claims, missing evidence, and recurrence.
- Make the auditor emit structured findings per audited layer and an `six_hour_auditor.audit_complete` handoff.
- Keep the auditor a reconciler first. Direct fixes must be bounded, evidence-backed, and recorded as ordinary repair/meta-repair transitions.
- Implement or harden stable problem ids, normalized signatures, occurrence counts, linked incidents, recurred-after-fix, status, ownership, and next review projection.
- Add compact committed summaries under `.megaplan/incident-ledger/summaries/`.
- Add GitHub sync for important transitions and persistent problems with redaction and size gates.
- Ensure editable-install branch/cloud runtime publication records source commit, branch, push status, install status, verification method, and recurrence.
- Add write-path redaction for append, brief generation, commit, and GitHub sync.
- Add tests for auditor missing-meta-repair evidence, stale watchdog reports, stale running repairs, persistent problem recurrence, redaction rejection, and GitHub projection formatting.
- Add cloud rollout/installation notes or automation so the active cloud machine can run the new wrappers.

Out:

- Do not turn GitHub into canonical incident state.
- Do not commit raw huge transcripts, provider payloads, or secret-shaped command output.
- Do not make the auditor run unbounded retries; it must hand off via expected transitions.

## Locked Decisions

- Six-hour auditor is a reconciler first, not a second independent control plane.
- Problem indexes are derived from events.
- GitHub sync publishes projections and links returned issue/PR/comment refs as evidence.
- Redaction is enforced before data reaches committed summaries or GitHub.

## Open Questions For Planner

- Exact threshold for opening/updating GitHub issues for persistent problems.
- Best normalized-signature algorithm for recurring problem ids.
- How to rotate/summarize `events.jsonl` without weakening the source-of-truth invariant.
- How to prove cloud runtime freshness in automated tests versus manual rollout verification.

## Done Criteria

- Six-hour auditor can explain what happened across project work, immediate repair, meta repair, install sync, and GitHub sync for fixture and live-style incidents.
- Persistent problem records update deterministically and show recurrence after claimed fixes.
- GitHub/editable-install publication is compact, redacted, and back-linked to ledger evidence.
- Auditor output contains enough structured evidence for a future repairer or human to understand the blocker without manual archaeology.
- Cloud rollout path is documented or automated and verified against the active runtime.
