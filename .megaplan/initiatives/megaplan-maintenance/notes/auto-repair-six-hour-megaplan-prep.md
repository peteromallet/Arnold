# Megaplan prep — maintenance control plane epic

Sources: the July 10 autofix/six-hour audit, completed resident architecture run `subagent-20260711-161224-0139c7b5`, existing initiative briefs/chain, and current authority contracts.

## Sizing and dependency rationale

This remains one epic because the end state is one maintenance control plane and the work exceeds two weeks. Five serialized milestones each fit roughly one sprint and produce an explicit contract handoff: containment → shared ledger/authority → independent verification → six-hour operational unblocker → 24-hour efficiency auditor. The two loops are separate products but not independent implementations: both require the M2 ledger/envelope, and M5 needs M4's closed watermarks and operational history.

The existing M1-M4 order is preserved. M4 is narrowed explicitly to the operational unblocker; M5 adds the resident analysis's future daily analytics recommendation without rewriting completed runtime history.

## Per-milestone dial choices

- M1 overall plan difficulty: 5/5; selected profile: `partnered-5`; because a bad containment plan can pass local tests while leaving a hidden cross-path mutation or false-report contract. `full/high @codex`.
- M2 overall plan difficulty: 5/5; selected profile: `partnered-5`; because the shared ledger, coherent observation envelope, evidence precedence, and transition authority are public cross-system contracts with non-local failure. `full/high @codex`, with directed prep.
- M3 overall plan difficulty: 5/5; selected profile: `partnered-5`; because fencing, recurrence, terminal custody, verification, canary install, and rollback are non-local production-safety contracts. `full/high @codex`.
- M4 overall plan difficulty: 4/5; selected profile: `partnered-4`; because exact-window scheduling, intervention suppression, and overlap are subtle, while M2-M3 have already fixed the architecture and authority. `full/high @codex`.
- M5 overall plan difficulty: 4/5; selected profile: `partnered-4`; because censored cohort analytics and clustering need careful decomposition, while the loop is strictly read-only and cannot affect active chain truth. `full/high @codex`.

Robustness remains `full` throughout: the work needs prep/critique/gate/review rigor, but no milestone has a concrete need for the rare `thorough` setting once authority-sensitive contracts are isolated into partnered-5 milestones. High author depth is justified by the long evidence set and structural reasoning. No xhigh/max is requested. Vendor is Codex for every milestone.

## Locked editorial decisions

- Run Authority and canonical TransitionWriter/repair custody remain authoritative; neither loop writes plan/chain truth.
- The six-hour loop can request bounded allowlisted action only through canonical custody and must use an independent verifier.
- The daily loop is analytics/recommendation only and cannot claim repair, change routing/profile/budget, or edit active chains.
- Both loops append to one ledger with separate operational, verification, and efficiency projections.
- Runtime remains default-off and source preparation is not rollout approval.

## Human gates retained

Backend/retention/access policy; identities/drift/lateness; SLOs and cohort dimensions; cost source; lease/grace; schedule offset/timezone; repair allowlist; canary/promotion/rollback ownership; ticket materialization and initiative-priority authority; sensitive-evidence handling.

## Launch state

Editorial preparation and validation only. No `megaplan init`, chain start/resume, cloud action, gate approval, finalize, execution, or babysit action is part of this work.
