# Settled-plan wave W1 synthesis — plan digest 03d0b91f

## Findings & dispositions
| # | Source | Finding | Disposition |
|---|---|---|---|
| K1 | CriticKiss [HIGH] | Drop catalog.py cutover of workers/omp.py | ACCEPT-PARTIAL. Rationale cited (fork violation) is factually wrong — workers/omp.py is Arnold-side, not fork. But YAGNI holds: onboarding does not need to refactor the worker. Decision: catalog.py stays as an onboarding-LOCAL table; workers/omp.py untouched anywhere in this run. |
| K2 | CriticKiss [MED] | Merge offer.py into flow.py | ACCEPT. flow.py owns guards+offer+orchestration. |
| K3 | CriticKiss [MED] | Inline verify into wire.py | ACCEPT. Persistence+verify share secret-safety concerns, one file. |
| K4 | CriticKiss [LOW] | Drop validation matrix for prose checklist | REJECT. agent_goal done-criterion 4 mandates criterion→evidence mapping; user demanded vigorous testing. Matrix stays. |
| K5 | CriticKiss [LOW] | Ship only 1–2 detection adapters | REJECT. Detection breadth IS the product requirement ("thorough in what it finds"); each adapter ~20 lines; framework cost already paid. |
| R1 | CriticRisk [P1] | Non-TTY byte-identical regression untested | ACCEPT. Golden-file stderr diff test in B4 + matrix row. |
| R2 | CriticRisk [P1] | Old-pin fallback (#16) untested | ACCEPT. PATH-without-omp test asserting original typed failure fires. |
| R3 | CriticRisk [P2] | No E2E secret-leak scan of pty capture | ACCEPT. Scan capture for key patterns post-flow. |
| R4 | CriticRisk [P2] | $HOME expansion unchecked at smoke level | ACCEPT. Assert written models.yml contains $HOME-expanded paths, no hardcoded /Users/. |
| R5 | CriticRisk [P2] | catalog.py parity untested until B4 | ACCEPT. B1 test asserts table keys/envKeys match workers/omp.py consumer expectations (read-only parity check). |

## Materiality
No finding reopens scope or architecture direction; all are module-layout simplifications (K2,
K3, K1-partial) and test additions (R1–R5). Plan remains coherent end-to-end → revise to v3,
run confirmation wave W2 per skill (prior wave produced accepted material simplifications).
