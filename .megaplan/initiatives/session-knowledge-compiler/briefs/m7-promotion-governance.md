---
type: brief
slug: m7-promotion-governance
title: Promotion Candidates, Applicability, and Review Authority
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M7 — Promotion Candidates, Applicability, and Review Authority

## Outcome

Implement a fail-closed, reviewable path from M6 session knowledge candidates
to project knowledge, binding accepted claims to primary evidence, deterministic
repository identity, explicit revision/path/environment applicability, and
authority-proportionate review decisions.

## In scope

- Define versioned promotion candidate, applicability, review request/decision,
  project-knowledge, and evidence-lineage records.
- Capture deterministic repository/project identity plus the narrowest supported
  commit, branch/version, path/module, environment, and time applicability.
- Resolve source claim, checkpoint, transcript/tool/file/commit/test evidence,
  actor, synthesis, and correction lineage before review.
- Define review tiers: narrow provisional claims may use bounded automated aid;
  authoritative, broad, security, migration, public-contract, or ambiguous
  claims require stronger declared authority/human gates.
- Support accept, reject, request-more-evidence, and narrow-applicability outcomes
  with actor, reason, evidence, and idempotency.
- Reject acceptance on missing identity/evidence/applicability/authority.
- Expose provisional/active decision records for M8 lifecycle processing.
- Produce `docs/session-knowledge-compiler/handoffs/m7-promotion-governance.md`.

## Out of scope

Contradiction matching/adjudication, supersession/invalidation lifecycle,
revision-aware retrieval behavior, backlog consolidation, and rollout.

## Locked decisions

- Session summaries are never inherently project-authoritative.
- Promotion is explicit, evidence-linked, reviewable, and fail-closed.
- Repository/revision applicability is mandatory; unknown never means global.
- Stronger authority and blast radius require stronger review.
- Accepted derived knowledge never outranks primary evidence in an audit.

## Open questions

- Which existing document/review substrate owns project knowledge without
  conflating it with tickets or generated plan state?
- Which identity survives local, worktree, cloud, rebased, and forked sessions?
- Which review tiers may be automated and where is human authority mandatory?
- How should branch/version applicability be represented before M8 lifecycle?

## Constraints

- Separate authorization for reading evidence and approving promotion.
- File/DB portability, append-only decisions, and no weakened destructive gate.
- Fail closed on ambiguous repo/revision identity or inaccessible evidence.
- No autonomous code/execution changes from promoted knowledge.

## Done criteria

- Acceptance cannot occur without source/evidence, identity, applicability, and
  sufficient review authority.
- Tests cover narrow acceptance, strong-review requirement, rejection,
  request-more-evidence, narrowed applicability, unauthorized review, and retry.
- Local/worktree/cloud identity fixtures resolve deterministically or fail closed.
- Every accepted record remains traceable to exact M1–M6 evidence/corrections.
- M7 handoff specifies active records and lifecycle hooks M8 must consume.

## Touchpoints

M6 candidate API, Store backends, repository/git identity helpers, existing
review/approval/authorization surfaces, initiative/document records, and tests
for identity, evidence, authority, applicability, and persistence.

## Anti-scope

Do not build organization-wide knowledge, contradiction engines, vector search,
autonomous code edits, ticket logic, or unversioned README authority.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m6-search-tools.md`,
landed candidate schema/search controls, and passing authorization/tool tests.
Only explicit M6 promotion candidates enter governance.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`;
directed prep enabled. A locally plausible promotion can become stale or
over-authoritative outside its source repository/revision.
