---
superseded_by: custody-control-plane
---

# Incident Control Plane DeepSeek Review Synthesis

Date: 2026-07-03

Input plan: `.megaplan/audits/incident-control-plane-plan-20260703.md`

Batch:

- Reviewer model: `deepseek:deepseek-v4-pro`
- Briefs: 20, one per load-bearing question
- Result: 20 succeeded, 0 failed
- Raw local results: `/tmp/incident-plan-question-review/results`

## Overall Verdict

The reviewers converged on the same high-level answer: the incident-ledger/control-plane concept is right, but the first draft was too conceptual in several operational places. Most reviews marked the relevant question as `PARTIAL`, not `WRONG`.

The main class of weakness was that the plan described useful nouns without enough agent-executable contracts: who writes exactly what, which event proves a transition, what deadline triggers the next actor, how evidence completeness is validated, and what counts as a shipped repair-system fix.

## Converged Required Updates

The plan was updated to add:

- Cloud ledger tie-break rule and derived-index regeneration contract.
- Atomic append/file-lock requirement for concurrent writers.
- `list --active` and `claim` commands for agent bootstrapping and duplicate-work prevention.
- Brief requirements for evidence validation, missing-evidence flags, and inline evidence summaries.
- Immutable event semantics.
- Minimum evidence requirements by event type.
- Additional event types: `repair_retriggered`, `meta_repair_failed`, `audit_complete`, and `secret_leak`.
- Scope decision rules for project, repair-system, run-state, infrastructure, and documentation fixes.
- Immediate-repair timeout and loop-breaking rule.
- Explicit six-hour auditor scheduling and completion/handoff contract.
- Actor responsibility sections for chain runner, install sync, and human events.
- Full shipped-fix chain: `source_fix_committed -> install_sync_applied -> repair_retriggered/relaunch -> verified_recovered`.
- Recurrence/problem-index schema.
- Redaction and size gates for committed summaries and GitHub sync.

## Important Reviewer Signals

Source of truth:
The plan needed an explicit cloud-over-local tie-break for cloud incidents and a rule that `problems.json` and `incidents.json` are derived from `events.jsonl`.

Writers:
The plan named `chain_runner`, `install_sync`, and humans as writers but did not give all of them responsibilities. It also needed a concurrency model for multiple writers.

Next action:
Reviewers asked for active incident discovery and claim/lock semantics so two agents do not act on the same expected event at once.

Avoiding archaeology:
The `brief` command needs to validate evidence refs and summarize evidence inline. Otherwise it risks becoming a list of paths that still requires manual log hunting.

Shipped repair-system fixes:
Reviewers strongly objected to treating `source_fix_committed` plus `install_sync_applied` as enough. The plan now requires retrigger and original-condition recovery verification.

Immediate/meta repair:
Reviewers asked for timeouts, failure schemas, a meta-repair failure branch, and a loop breaker. The plan now adds a default 15-minute/two-attempt immediate-repair limit unless new evidence appears.

Six-hour auditor:
Reviewers asked for a concrete trigger, output contract, coordination rule with meta repair, and completion event.

Recurring problems:
Reviewers asked for a concrete `problems.json` schema and stable signature generation rather than only saying `problem_id`.

Redaction:
Reviewers asked for executable redaction/size gates and a leak recovery path.

## Remaining Design Choices

These are still implementation choices, not blockers to the plan:

- Exact command namespace: `megaplan incident ...` versus standalone `incident ...`.
- Exact normalized-signature algorithm for `problem_id`.
- Exact file rotation policy for large `events.jsonl`.
- Whether GitHub sync opens issues for every persistent problem or only recurrent/high-severity problems.
- Whether `system` remains a first-class actor or is reserved for migration/integrity events.
