---
id: 01KYVKPN6JHD19ZRM3WQF9XV8S
title: Provide backend-neutral WBC persistence and canonical deployed-evidence joins
status: open
source: human
tags:
- platformization
- wbc
- postgres
- sqlite
- evidence-lineage
- follow-up
codebase_id: null
created_at: '2026-07-31T08:12:26.706517+00:00'
last_edited_at: '2026-07-31T08:12:36.899493+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: null
  linked_at: 2026-07-31 08:12:35.738980+00:00
- epic_id: native-platform-followup
  resolves_on_complete: false
  kind: associated
  provenance: null
  linked_at: 2026-07-31 08:12:36.899476+00:00
---

The current cloud runtime records phase WBC in plan-local SQLite and does not expose a backend-neutral evidence reader or a single immutable join across native journal, WBC, acceptance, checkpoint/reentry, and deployed runtime identity.

After the narrow custody-release canary is proven on its actual supported SQLite backend, make this product-neutral through the Native Parity and Platformization work:

- define one backend-neutral read-only WBC query/store protocol with SQLite and PostgreSQL conformance fixtures;
- make every durable phase, revise/rework, suspension, resume, tiebreaker child, and terminal acceptance use the same attempt identity and lifecycle vocabulary;
- join manifest/graph revision, run and invocation/reentry IDs, checkpoint cursor, acceptance transaction/snapshot/verdict, source revision, runtime identity, and deployment attestation without heuristic stitching;
- freeze content-addressed evidence windows and let an independent consumer re-derive verdicts;
- retire direct SQLite assumptions, split JSON receipts, and product-local lifecycle readers only after two-consumer parity and restore/replay drills pass;
- preserve the narrow release canary as a consumer fixture during migration.

This is not the immediate release blocker: ticket 01KYVJ7A47TMH4BRGEV9JFTK10 owns the concrete current-backend canary. Acceptance here is backend parity, two independent consumers, cross-stitch/restore/replay negatives, and no competing lifecycle writer.
