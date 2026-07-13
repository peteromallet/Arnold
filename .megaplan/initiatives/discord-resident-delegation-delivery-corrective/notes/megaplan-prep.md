# Megaplan Prep and Rubric

## Sizing

The work spans ingress identity, persistence, concurrency, process launch, Discord outbound delivery, recovery, migration, and operations. It is larger than one two-week plan and is decomposed into six sequential sprints, each intended to fit within roughly two skilled-engineer weeks. Each milestone hands forward an executable contract or implementation surface used by the next.

## Per-milestone selections

- M1 difficulty 5/5; profile `all-codex`; bad ledger/transition contracts could pass local tests while creating non-local loss or duplication. Robustness `full`, depth `high`.
- M2 difficulty 5/5; profile `all-codex`; durable ingest ordering, quarantine/CAS promotion, scanning policy, and burst attribution can fail across database/filesystem/network boundaries while local tests still pass. Robustness `full`, depth `high`.
- M3 difficulty 5/5; profile `all-codex`; duplicate execution, restricted attachment isolation, explicit capture/selection, and stale-worker fencing are security and production-integrity boundaries shared by every resident caller. Robustness `full`, depth `high`.
- M4 difficulty 5/5; profile `all-codex`; deterministic multipart batching, immutable byte custody, partial delivery, and ambiguous Discord outcomes require careful reconciliation without duplicate visible effects. Robustness `full`, depth `high`.
- M5 difficulty 5/5; profile `all-codex`; startup recovery, reference-based GC, holds/privacy, legacy voice/image/manifest compatibility, and reversible cutover can lose data or split authority despite locally green code. Robustness `full`, depth `high`.
- M6 difficulty 5/5; profile `all-codex`; adversarial proof must detect bypasses across normal, repair, scheduler, todo, reaper, and compatibility paths while enforcing the security/rollout gate. Robustness `full`, depth `high`.

The user explicitly requires all-Codex, so every milestone pins `profile: all-codex` and `vendor: codex`. Full robustness is retained: the audit findings, target invariants, sequencing, and acceptance evidence are already explicit, so the rubric does not justify the extra parallel critique cost of thorough/extreme. High depth is justified by cross-process ordering, crash consistency, and migration reasoning. No feedback phase or bake-off is needed.
