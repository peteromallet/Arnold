# Isolated review 2 — concrete PR and migration sequencer

Working directory: `/Users/peteromalley/Documents/Arnold`.

Read-only review: do not edit repository files or git state. Do not read `.tmp/native-parity-sensecheck-round2/final-audit.md` or any reviewer output. Inspect primary files and actual code yourself; cite exact `path:line` evidence.

Read `docs/arnold/megaplan-native-representation-report.md`, `docs/arnold/megaplan-native-parity-corrective-plan.md`, the Native Parity initiative README/NORTHSTAR/chain, all seven active sprint briefs, and actual workflow/lowering/compiler/runtime/components/handlers/auto/CLI/suspension/proof/scenario/test surfaces. M11 Custody substrate is locked complete and out of scope.

Translate S1–S7 into an ordered sequence of repository-level PR slices. Inventory exact producers, consumers, adapters, route readers/writers, test oracles, installed-artifact paths, and compatibility surfaces, with `path:line` citations. Find phases where the repo cannot stay runnable, dual-run semantics are ambiguous, producer relocation/deletion ordering is unsafe, or a sprint lacks a binary stop/go receipt. Provide: (1) dependency graph, (2) safe strangler order, (3) per-PR stop/go receipts, (4) rollback points, (5) minimal plan amendments only where epic wording must change. Do not restate objectives. Separate sprint-planning detail from true epic ambiguity. Take a position.
