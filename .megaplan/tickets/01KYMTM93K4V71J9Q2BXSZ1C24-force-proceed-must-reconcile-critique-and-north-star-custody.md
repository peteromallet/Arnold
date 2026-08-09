---
id: 01KYMTM93K4V71J9Q2BXSZ1C24
title: Force-proceed must reconcile critique and North Star custody
status: open
source: human
tags:
- bug
- custody
- force-proceed
- state-machine
- regression
- post-m11
- blocked-by-m11
- managed-recovery-custody
- immediate-residual
codebase_id: null
created_at: '2026-07-28T16:58:47.796114+00:00'
last_edited_at: '2026-07-31T03:17:11+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-reconciliation-20260731
  linked_at: '2026-07-31T03:17:11+00:00'
---

Observed while forcing custody-control-plane M11 forward: force-proceed advanced the phase and recorded debt, but left critique custody and the blocking North Star action unresolved. Finalize then consumed stale pre-force blockers. Forced progress must retain explicit debt while atomically reconciling the authoritative critique and North Star custody projections.\n\nSequencing: execute only from a follow-up epic after custody-control-plane M11 plan m11-cross-contract-acceptance-20260728-1035 has completed. Do not execute or fold this ticket into the current epic.\n\nRegression acceptance:\n- Reproduce a blocked phase with pending critique findings and a blocking North Star action.\n- force-proceed gives every pending item an explicit durable disposition and updates authoritative custody in the same transition.\n- Finalize and execute do not fail on stale pre-force custody metadata.\n- Retrying the same force is idempotent with no duplicate debt or events.\n- Findings remain auditable and unrelated authorization checks remain enforced.

## 2026-07-31 implementation evidence

Implemented in `635f967d80`. Force-proceed now builds complete critique and
North-Star dispositions before mutation, commits them in the same state CAS,
and projects derived custody artifacts only after that CAS succeeds. Retries
are idempotent and do not duplicate debt.

Focused regressions cover atomic disposition, failed-CAS non-publication,
idempotent retry, and finalize consumption of reconciled custody.

Keep this ticket open until the exact archived M11 force-proceed trace has been
replayed and its WBC receipt inspected. No additional scoped code residual is
currently known.

Native Parity S6 is an associated regression consumer, not the resolver of this
remaining release proof. The Critique Ledger epic owns cumulative semantic
finding reconciliation; it does not own force-proceed transition custody and
must not auto-close this ticket.
