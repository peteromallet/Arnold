---
superseded_by: custody-control-plane
---

# Tiered Repair Hardening

This initiative turns the tiered repair/audit design into five aggressive two-week megaplan sprints.

The plan was challenged by five Codex reviewers:

- scope and sprint decomposition;
- data contract and state semantics;
- cloud operability and rollback;
- human escalation, redaction, auth safety;
- testability, rollout, and conformance.

The resulting judgment is:

- keep five sprints as the execution roadmap;
- make sprints 1-3 the mandatory repair core;
- move resolver, lock, redaction, escalation preservation, feature flags, and rollback gates earlier;
- keep meta-repair and six-hour auditor autonomy behind explicit gates and flags.

Milestones:

1. `m1-cloud-safe-substrate`: contract kernel, resolver observe mode, shared lock, redaction, escalation ledger skeleton, feature flags, rollback runbook.
2. `m2-repair-correctness`: existing one-hour repair loop gets lock enforcement, non-liveness verification, 60-minute budget, and true-human-blocker proof.
3. `m3-triggered-repair`: request queue, dedupe, stale suppression, trigger wrapper, watchdog queue scan, and highest-signal hooks.
4. `m4-human-workflow-cloud-hardening`: answer/resume escalation workflow, Discord/resident auth linkage, supersession, cloud smoke gates, operator docs.
5. `m5-meta-audit-intelligence`: meta-repair MVP, auditor cross-references, root-cause patterns, bounded fixes, retention/index cleanup, rollout signoff.

Review notes and challenge synthesis are in `notes/challenge-synthesis.md`.
