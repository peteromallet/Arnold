# Epic Handoff Contract

Every milestone must leave one reviewed, content-addressed handoff for its
successor. The handoff is an implementation artifact produced during future
execution; these planning assets define its minimum shape.

## Required fields

- schema/version, milestone label, implementation revision, target revision,
  producer plan/run identity, North Star digest, brief digest, and timestamp;
- frozen public/internal contracts and exact schema/API revisions;
- implementation touchpoints and migrations actually landed;
- machine-readable test commands and result/evidence artifact paths;
- coverage/conformance matrix revision and explicit unknown/not-applicable rows;
- open decision-gate receipts and whether each is satisfied, scoped, deferred,
  or blocks the successor;
- compatibility, rollout flag, failure-isolation, rollback, and data-migration
  behavior; and
- unresolved risks/gaps, anti-scope confirmation, reviewer identity/decision,
  and a digest over the handoff and proof artifacts.

## Acceptance rule

A successor may start only when its predecessor handoff exists, hashes resolve,
the reviewer decision is accepted, required gate receipts are satisfied, and no
blocking gap contradicts the successor brief. Mutable status prose, a passing
subset, an agent completion message, or a PR/commit alone does not satisfy the
handoff.

## Artifact map

| Milestone | Required path | Successor contract |
|---|---|---|
| L1 | `docs/managed-agents/handoffs/l1-lifecycle-contract.json` | v3 package/schema/journal/capability contracts and gate receipts for L2 |
| L2 | `docs/managed-agents/handoffs/l2-v2-v3-parity.json` | resident/automatic seam flags, parity/anomaly, exclusion, restart/delivery, rollback proof for L3 |
| L3 | `docs/managed-agents/handoffs/l3-megaplan-cutover.json` | worker seam, launch registry, phase parity, rollback, compiler ownership matrix for C1 |
| C1 | `docs/session-knowledge-compiler/handoffs/c1-accepted-checkpoints.json` | observation/source/cursor/trigger/claim/atomic checkpoint contract for C2 |
| C2 | `docs/session-knowledge-compiler/handoffs/c2-four-record-contract.json` | four schemas, evidence validation, bounded direct-Pro route, prior-context API for C3 |
| C3 | `docs/session-knowledge-compiler/handoffs/c3-synthesis-search-controls.json` | projection/correction/query/control and promotion-candidate APIs for C4 |
| C4 | `docs/session-knowledge-compiler/handoffs/c4-promotion-governance.json` | applicability/review/contradiction/supersession APIs and paper-cut inputs for C5 |
| C5 | `docs/session-knowledge-compiler/handoffs/c5-completion-evidence.json` | final North Star traceability, conformance, offline replay, operational gates and known limits |

The final C5 artifact is completion evidence for the implementation epic, not a
deployment, production-enable, observation-window, or path-retirement receipt.
