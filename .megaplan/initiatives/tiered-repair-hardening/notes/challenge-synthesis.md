---
superseded_by: custody-control-plane
---

# Codex Challenge Synthesis

Five Codex challenge passes were run before committing this chain shape. The reviewers agreed that the original eight-stage implementation inventory is directionally right, but the executable sprint order needed adjustment.

## Key Corrections

- Do not write immutable repair evidence before a minimal current-target resolver and shared lock exist.
- Do not let failure-triggered repair amplify stale markers or races; request queue work needs resolver-backed dedupe and lock semantics first.
- Do not defer human escalation preservation to the end; escalation ledger/current-pointer semantics need to exist before earlier sprints emit or clear human questions.
- Do not route confidence through one huge wrapper test file. Put schema, resolver, lock, redaction, dedupe, and classification semantics in Python module tests; keep wrapper tests as adapter/scenario smoke.
- Do not enable meta-repair/autonomous audit fixes by default. Land them as gated, feature-flagged paths with focused tests and post-retrigger verification.
- Cloud rollout needs explicit preflight, rollback, old-sidecar compatibility, feature flags default-off, and per-sprint smoke evidence.

## Resulting Sprint Shape

The five-sprint chain is still appropriate, but the first three sprints are the mandatory core:

1. Cloud-safe substrate: contract, resolver, lock, redaction, escalation preservation, flags, rollback.
2. Existing repair correctness: verification semantics, 60-minute envelope, true-human-blocker proof.
3. Failure-triggered repair: request queue, dedupe, trigger wrapper, narrow hooks.

The last two are gated expansions:

4. Human workflow and cloud hardening: answer/resume flow, Discord/resident auth, supersession, cloud smoke.
5. Meta-repair and auditor intelligence: meta-repair, cross-references, bounded fixes, retention/indexing.

## Feature Flags

Every behavior-changing layer should have a default-off or observe-only rollout mode:

- `REPAIR_CONTRACT_WRITE_ENABLED`
- `REPAIR_RESOLVER_ENFORCE`
- `REPAIR_REQUESTS_OBSERVE_ONLY`
- `REPAIR_TRIGGER_ENABLED`
- `ESCALATION_LEDGER_ENABLED`
- `META_REPAIR_ENABLED`
- `AUDIT_AUTOFIX_ENABLED`

The exact names may change during implementation, but the capability split should not.

## Acceptance Gates

Each sprint should leave:

- validated artifacts;
- recorded resolver decisions;
- no raw secret-shaped text in prompts/reports/Discord summaries;
- append-only ledgers not rewritten;
- lock required for mutation;
- no terminal success from process liveness alone;
- old sidecars and reports still readable;
- cloud smoke or fixture evidence appropriate to the sprint.
