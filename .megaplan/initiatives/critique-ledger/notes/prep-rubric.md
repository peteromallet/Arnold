# Megaplan prep and per-sprint rubric

The critique-ledger implementation is larger than one two-week plan and has
strict sequential dependencies: contract/early M6 semantic-loop gate → WBC-backed
persistence/replay → routing/briefing → role-flow reconciliation → coordinated
cutover/retirement. Each
sprint is intended to fit roughly two weeks of skilled human engineering,
including implementation, tests, review, and the written handoff.

The default remains `partnered-5/full`. No sprint steps down in profile because
incorrect decomposition or task adjudication can suppress evidence while local
tests remain green. `thorough` is used only for the specifically named public
contract/schema-migration and cutover/custody risks. Medium depth is used
where the architecture is locked but multi-stage integration still needs real
deliberation; high depth is reserved for contract/migration decisions.

| Sprint | Difficulty | Profile | Robustness | Depth | Prep direction | One-sentence justification |
|---|---:|---|---|---|---|---|
| CL1 Contract and M6 oracle | 5/5 | partnered-5 | thorough | high | Revalidate landed WBC and current critique contracts; freeze M6 and prove the thin semantic loop. | A mistaken boundary/schema oracle could make all downstream work internally consistent but globally wrong. |
| CL2 Ledger persistence and replay | 5/5 | partnered-5 | thorough | high | Inspect WBC persistence/custody and the one-time import seam from the CL1 handoff. | Append-only persistence and import failures can silently lose or reinterpret findings. |
| CL3 Evaluator routing and briefings | 5/5 | partnered-5 | full | medium | Trace evaluator selection, fanout, prompt projection, budgets, and model routing while preserving CL1/CL2. | Context selection and overflow defects can suppress evidence even when all workers succeed. |
| CL4 Reconciliation/reviser/gate | 5/5 | partnered-5 | full | medium | Trace evaluator validation, flag lifecycle, revise metadata, gate carry/signals, finalize custody, and receipts. | The role-flow spans several authorities and can silently omit disposed findings or over-promote model judgment. |
| CL5 Coordinated cutover and retirement | 5/5 | partnered-5 | thorough | high | Revalidate exact revisions, M6/integrated-loop gates, WBC custody, backup/restore, and the atomic cutover checklist. | This single authority-changing boundary must prevent false convergence and preserve recoverable custody. |

All sprints use `vendor: codex`, `deepseek_provider: direct`, and explicit prep.
Critique/review workers retain the selected profile's asymmetrical sense-check
depth. No feedback phase or bakeoff is requested. The chain is review-gated,
does not auto-approve execution, and stops on failure or escalation.
