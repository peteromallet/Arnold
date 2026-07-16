# Megaplan prep and per-sprint rubric

The critique-ledger implementation is larger than one two-week plan and has
strict sequential dependencies: contract/oracle → persistence/replay → routing/
briefing → role-flow reconciliation → shadow proof → canary/conformance. Each
sprint is intended to fit roughly two weeks of skilled human engineering,
including implementation, tests, review, and the written handoff.

The default remains `partnered-5/full`. No sprint steps down in profile because
incorrect decomposition or task adjudication can suppress evidence while local
tests remain green. `thorough` is used only for the specifically named public
contract/schema-migration and rollout/mixed-version risks. Medium depth is used
where the architecture is locked but multi-stage integration still needs real
deliberation; high depth is reserved for contract/migration decisions.

| Sprint | Difficulty | Profile | Robustness | Depth | Prep direction | One-sentence justification |
|---|---:|---|---|---|---|---|
| CL1 Contract and M6 oracle | 5/5 | partnered-5 | thorough | high | Revalidate landed WBC and current critique contracts; freeze the exact M6 corpus and ownership map. | A mistaken boundary/schema oracle could make all downstream work internally consistent but globally wrong. |
| CL2 Ledger persistence and replay | 5/5 | partnered-5 | thorough | high | Inspect file/Store/WBC persistence, custody, schema-version readers, and migration seams from the CL1 handoff. | Append-only persistence and mixed-version migration failures can silently lose or reinterpret findings. |
| CL3 Evaluator routing and briefings | 5/5 | partnered-5 | full | medium | Trace evaluator selection, fanout, prompt projection, budgets, and model routing while preserving CL1/CL2. | Context selection and overflow defects can suppress evidence even when all workers succeed. |
| CL4 Reconciliation/reviser/gate | 5/5 | partnered-5 | full | medium | Trace evaluator validation, flag lifecycle, revise metadata, gate carry/signals, finalize custody, and receipts. | The role-flow spans several authorities and can silently omit disposed findings or over-promote model judgment. |
| CL5 Offline comparison and shadow | 5/5 | partnered-5 | full | medium | Inventory experiment, metrics, feature-flag, and report-only sidecar patterns before running the frozen corpus. | Confounding and shadow side effects can produce a convincing but invalid acceptance result. |
| CL6 Canary and conformance | 5/5 | partnered-5 | thorough | high | Revalidate WBC, mixed-version readers, flags, rollback mechanisms, and all handoff hashes before canary. | This is the explicit public compatibility/rollout boundary where a false pass changes production critique behavior. |

All sprints use `vendor: codex`, `deepseek_provider: direct`, and explicit prep.
Critique/review workers retain the selected profile's asymmetrical sense-check
depth. No feedback phase or bakeoff is requested. The chain is review-gated,
does not auto-approve execution, and stops on failure or escalation.
