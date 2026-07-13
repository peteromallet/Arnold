---
type: decision
slug: single-authoritative-runtime-history
status: proposed-human-gate
date: 2026-07-11
---

# Post-WBC custody convergence approval

## Proposed decision

Approve one bounded custody follow-up after Workflow Boundary Contracts (WBC):
adapt the existing custody resolver and Megaplan cloud-chain custody consumers to
the exact landed WBC boundary/attempt/effect contracts and Run Authority views.
No custody-local ledger, lifecycle, status authority, writer API, or portfolio-
wide migration is approved.

## Locked ownership

- WBC owns boundary declarations, attempt/effect evidence, semantic findings,
  payload/reference policy, and its support/conformance manifest.
- Run Authority owns grants, accepted attempts and decisions, fences,
  quarantine, and accepted operational views.
- Custody owns coherent evidence collection plus the fail-closed policy used by
  resolver, status/current-target, watchdog, repair dispatch, and independent
  recovery verification for the declared Megaplan cloud-chain surface.
- M1-M4 are completed foundation and remain historical lineage, not new work.

## Approval record required before launch

A human approver must replace the frontmatter state with the approved state only
after recording all of the following in this file or an immutable referenced
artifact:

- the validated WBC completion-manifest digest and landed interface hashes;
- the exact in-scope cloud-chain call-site inventory;
- freshness/lag thresholds and unknown/incoherent behavior;
- repair allowlist, canary cohort, kill switch, and rollback owner;
- confirmation that production enforcement and mutating repair start disabled;
- confirmation that no ownership conflict requires a WBC or Run Authority change.

Absent that record, the chain launch precondition must remain unsatisfied.
Milestone completion or PR merge does not approve later production enforcement,
provider/Git effects, or legacy deletion.
