# Megaplan Prep and Rubric

## Sizing

The work spans ingress identity, persistence, concurrency, process launch, Discord outbound delivery, recovery, migration, and operations. It is larger than one two-week plan and is decomposed into six sequential sprints, each intended to fit within roughly two skilled-engineer weeks. Each milestone hands forward an executable contract or implementation surface used by the next.

## Per-milestone selections

- M1 difficulty 5/5; profile `all-codex`; bad ledger/transition contracts could pass local tests while creating non-local loss or duplication. Robustness `full`, depth `high`.
- M2 difficulty 5/5; profile `all-codex`; crash ordering and burst attribution have subtle concurrency failures. Robustness `full`, depth `high`.
- M3 difficulty 5/5; profile `all-codex`; duplicate execution and stale-worker side effects are production integrity risks. Robustness `full`, depth `high`.
- M4 difficulty 5/5; profile `all-codex`; ambiguous transport outcomes and exactly-once-visible delivery require careful reconciliation. Robustness `full`, depth `high`.
- M5 difficulty 5/5; profile `all-codex`; startup recovery and backward-compatible cutover can damage service despite locally green code. Robustness `full`, depth `high`.
- M6 difficulty 4/5; profile `all-codex`; adversarial evidence and staged rollout span several surfaces but operate against locked contracts. Robustness `full`, depth `high`.

The user explicitly requires all-Codex, so every milestone pins `profile: all-codex` and `vendor: codex`. Full robustness is retained: the audit findings, target invariants, sequencing, and acceptance evidence are already explicit, so the rubric does not justify the extra parallel critique cost of thorough/extreme. High depth is justified by cross-process ordering, crash consistency, and migration reasoning. No feedback phase or bake-off is needed.
