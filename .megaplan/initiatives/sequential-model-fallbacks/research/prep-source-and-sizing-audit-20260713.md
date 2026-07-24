# Preparation Source and Sizing Audit

Date: 2026-07-13 (UTC)
Layout: `megaplan-initiatives-v1`
Initiative: `sequential-model-fallbacks`

## Reuse decision

Canonical CLI searches for both the rough title (`unified managed-agent profiles sequential fallbacks`) and rough slug (`sequential model fallbacks`, all keywords) returned this initiative as the sole 1.0 match. Its existing North Star, fallback research, decision record, and two milestone briefs already own the requested resolver, fallback, custody, nested-launch, migration, and conformance outcome. Reuse in place is mandatory; a second initiative would create competing routing and custody authority.

## Source baseline inspected

Preparation inspected the project worktree at `/workspace/arnold`, the pinned resident runtime at `/workspace/resident-runtime-e6c63c6e61`, and the Discord corrective initiative. This is a planning baseline, not authorization to reconcile, publish, deploy, or change runtime code.

- `arnold_pipelines/megaplan/profiles/partnered-5.toml` already supplies D1-D10 execute routing and ordered arrays at D7-D8. Scalar and array behavior are therefore compatibility inputs, not greenfield design.
- `arnold_pipelines/megaplan/fallback_chains.py` already owns `FallbackSpecChain`, compact phase-model encoding, provider-family identity, retry classification, observability fields, and an explicit unsafe execute-fallback error. The epic should converge callers on these primitives and add mutation/accounting evidence rather than introduce another fallback engine.
- `arnold_pipelines/megaplan/resident/subagent.py` still owns a separate Luna/Terra/Sol D1-D10 `route_delegated_task` policy and a resident-specific durable launcher/manifest. This is the concrete duplicate resolver/adapter authority the epic must migrate.
- `arnold_pipelines/megaplan/managed_agent.py` already declares `arnold-managed-agent-run-v2` and provides a neutral durable process lifecycle for resident and automatic repair work: stable identity, manifest/history, PID evidence, result/log paths, retry lineage, and terminal transitions. It does not yet provide the complete root-task custody, shared resolver receipt, descendant authority, or root-tree budgets required by the North Star. The target must extend this contract compatibly or choose the next additive revision after characterization; it must not invent a conflicting second “v2.”
- `arnold_pipelines/megaplan/resident/provenance.py` already validates `arnold-resident-delegation-provenance-v1`. The managed-agent contract consumes and propagates it immutably; Discord delivery ownership remains in `discord-resident-delegation-delivery-corrective`.
- The project and pinned runtime match on the inspected fallback, profile, provenance, fanout, and managed-agent lifecycle files. The pinned runtime differs in `resident/subagent.py`: it adds bounded context-directory routes, task/prompt size guards, runtime-revision capture, and prompt injection that are absent from the project checkout. This drift is an explicit compatibility/reconciliation gate before resident-code changes.
- `chain.yaml` intentionally targets `editible-install`. The local branch exists, while `origin/editible-install` resolves to the supplied pinned runtime revision `e6c63c6e61736bb108f2166f265d49708a38d3ae`; later execution must refresh/reconcile deliberately. Preparation does not move branches or update refs.

## Sizing decision

Retain exactly two milestones, but resize each to roughly two human-weeks (about ten skilled-engineer days), for an initiative total of roughly four human-weeks.

The previous days 1-6 / days 7-10 schedule was undersized. Sprint 1 must characterize and freeze four coupled public contracts across multiple dispatchers; Sprint 2 must add transactional enforcement, migrate each dispatcher and schema, prove restart behavior, and close a cross-dispatcher conformance/rollout gate. Those are not credible five-day slices even with parallel work.

Restoring the older seven serial milestones would over-serialize work that can proceed independently. The right dependency graph remains:

```text
Sprint 1 parallel tracks
resolver/profile | fallback safety | custody/schema | launch state machine
                              |
                              v
docs/managed-agents/s1-contract-handoff.yaml
                              |
                              v
Sprint 2 parallel tracks
authority/budgets | dispatcher migration/restart | conformance/rollout
                              |
                              v
final machine-readable conformance gate
```

The Sprint 1 handoff must identify and hash the frozen contract documents, schemas, fixtures, project/base revision, pinned runtime revision, and focused test evidence. Sprint 2 must fail closed on a missing or stale handoff.

## Sprint dial selections

| Sprint | Difficulty | Profile | Robustness | Depth | Modifiers | Justification |
|---|---:|---|---|---|---|---|
| S1 shared foundations and managed launch | 5/5 | `partnered-5` | `full` | `high` | `@codex +prep` | A bad resolver/schema/mutation-gate plan can pass local tests while creating incompatible public safety contracts across divergent dispatchers; high author depth is warranted for baseline reconciliation and interface freeze. |
| S2 enforcement, integration, and rollout | 5/5 | `partnered-5` | `full` | `high` | `@codex +prep` | Concurrency, crash recovery, dual-read cutover, and cross-dispatcher conformance can look green while violating custody or non-expanding authority; high author depth is warranted for integration and false-pass analysis. |

`full` is retained rather than raised to `thorough`: the briefs are self-contained, production rollout remains disabled, and each sprint already has explicit handoff/conformance gates. Neither sprint needs xhigh/max. Prep remains enabled and narrowly directed at current-state characterization and baseline reconciliation.

## Locked handoff and final evidence

- Sprint 1: `docs/managed-agents/s1-contract-handoff.yaml` plus the resolution, fallback, custody/schema, and child-launch contracts and their machine-readable fixtures.
- Sprint 2: the tree-policy/budget and migration/operations contracts; dispatcher parity and restart evidence; `docs/managed-agents/north-star-traceability.yaml`; `docs/managed-agents/managed-agent-conformance.yaml`; its validator; and an initiative-local proof map under `assets/`.
- The chain records the only cross-sprint dependency (`s2` depends on `s1`) and a required final conformance gate. Parallel tracks are prose/task-DAG requirements; `chain.yaml` remains serial in milestone order.

## Genuine unknowns retained for planning/execution

- Whether existing managed v2 can absorb the new custody/tree fields compatibly or needs the next schema revision.
- Whether current execute seams can prove an affirmative pre-first-mutation boundary; absent that proof, v1 execute fallback remains blocked after the primary attempt.
- The smallest additive Discord provenance/root-completion seam, if the current corrective contracts lack a generic field required by the frozen managed-agent contract.
- Exact provider/model catalog entries, production dollar/token/time limits, any structural-limit increase, canary population, and cutover date. These remain operator decisions and do not block implementation or shadow-mode readiness.
- The exact compatibility window for resident-v1/current-managed-v2 records, resolved from real fixture inventory and restart evidence during Sprint 2.

No chain, cloud run, init, implementation, deployment, push, or PR was started by this preparation audit.
