---
type: brief
slug: c4-promotion-governance
title: Project Knowledge Promotion and Contradiction Governance
epic: session-knowledge-compiler
created_at: '2026-07-13T20:36:41.554396+00:00'
---

# C4 — Project Knowledge Promotion and Contradiction Governance

## Outcome

Implement a cautious, reviewable path from session-scoped reusable knowledge to
project knowledge. Every promoted claim retains primary evidence and explicit
repository/version/commit applicability, detects contradictions, and receives
review strength proportionate to its authority and blast radius.

## Source and prerequisite

Promotion and evidence-primary decisions were recovered from resident messages
`msg_63610d4bb911` and `msg_5d47dbb7a366` and are locked in the North Star.
Require reviewed
`docs/session-knowledge-compiler/handoffs/c3-synthesis-search-controls.json`;
its `propose-promotion` candidate, correction, hierarchical lineage,
authorization, and scoped-search contracts are prerequisites. G7 promotion
review tiers must be approved before accepted promotion writes.

## In scope

- Define versioned promotion candidate, review decision, project knowledge,
  applicability, contradiction, supersession, and invalidation records.
- Require repository/project identity plus the narrowest supportable commit,
  branch, version, path/module, environment, and time applicability. Unknown
  applicability must stay explicit rather than becoming global by omission.
- Resolve and retain all session claim, checkpoint, transcript/tool/file/commit/
  test evidence and correction lineage for every promotion.
- Detect potential contradictions against active project knowledge and relevant
  candidates. Do not auto-merge incompatible claims; present the conflict and
  evidence to the reviewer.
- Establish tiered review policy. Claims marked authoritative, broad, security/
  migration/public-contract sensitive, or contradictory require stronger review
  than narrow provisional guidance. Automated review may assist but cannot
  silently self-approve beyond its declared authority.
- Support accept, reject, request-more-evidence, supersede, narrow-applicability,
  and invalidate outcomes with actor/reason/evidence.
- Make search return project knowledge only when the caller's repository and
  revision fall within applicability; otherwise return it as out-of-scope or
  potentially stale, not as active truth.
- Ensure transcript/tool evidence remains the primary audit trail even after
  project promotion.

## Out of scope

- Cross-project/global organizational knowledge promotion.
- Paper-cut dedup/prioritization and operational proof (C5).
- Automatically changing code or execution decisions based solely on promoted
  knowledge.

## Locked decisions

- Promotion is explicit and reviewable; a session summary is never inherently
  project-authoritative.
- Repository/version/commit applicability is mandatory for accepted knowledge.
- Contradictions are preserved and adjudicated, not silently overwritten by the
  newest or most confident synthesis.
- Stronger authority demands stronger review.
- Derived project knowledge never outranks primary transcripts/tool/file/commit/
  test evidence in an audit.
- Corrections and invalidations are append-only; historical accepted versions
  remain traceable.

## Open questions for the planner

- **G7, product/security owners:** define which narrow provisional claims may
  use bounded automated review assistance and which risk classes require human
  authority. Missing approval blocks accepted promotion writes.
- Which existing initiative/document/review substrate should own project
  knowledge without conflating it with tickets or Megaplan generated state?
- What deterministic repository/revision identity is available in resident,
  local, worktree, and cloud sessions?
- Which review tiers can be automated safely and which require human approval?
- How should branch divergence and later rebases affect commit applicability?
- When should code/test changes automatically flag knowledge as potentially
  stale without claiming a contradiction?

## Constraints

- Fail closed on missing repository identity, evidence, or applicability.
- Authorization to read source evidence and approve promotions must be enforced
  independently.
- Do not duplicate or weaken existing destructive-action/human approval rules.
- Preserve compatibility and portability across file and DB stores.
- Contradiction checks must be bounded, explainable, and evidence-producing.

## Touchpoints

C3 tool/search APIs; Store backends; git/repository identity helpers; initiative
and resident context surfaces; existing review/approval/authorization modules;
search indexes; and tests for repository/worktree/cloud applicability,
contradiction, authorization, and supersession.

## Measurable done criteria

- Promotion cannot be accepted without source claim/evidence, repository
  identity, and explicit applicability.
- Tests cover narrow acceptance, stronger authoritative review, rejection,
  request-more-evidence, contradiction blocking, narrowed applicability,
  supersession, invalidation, and corrected source claims.
- Search at an applicable revision returns active knowledge with provenance;
  search outside the range marks it stale/out-of-scope and does not present it
  as current fact.
- Two contradictory candidates remain independently traceable and require a
  recorded adjudication before either becomes active authoritative knowledge.
- Primary evidence remains resolvable after promotion and after later
  supersession/invalidation.
- `docs/session-knowledge-compiler/handoffs/c4-promotion-governance.json`
  records applicability, review-tier, contradiction/adjudication, drift,
  supersession/invalidation, project-query, and immutable paper-cut interfaces
  and is reviewed for C5.

## Anti-scope

Do not build organization-wide ontology, vector-search infrastructure unrelated
to this product, or autonomous code changes from knowledge records. Do not turn
initiative README files into an unversioned authority database.

## Estimate and run shape

Approximately two skilled-human weeks. Overall plan difficulty 5/5; profile
`partnered-5`; robustness `full`; depth `high`; directed prep. Stale,
contradictory, or over-authorized promoted knowledge can look locally valid
while misleading work outside the producing run.
