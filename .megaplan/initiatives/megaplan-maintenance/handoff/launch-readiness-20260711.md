# Editorial launch-readiness handoff

The initiative is shaped as a five-milestone, human-gated chain. It is intentionally unlaunched and makes no claim that paused/in-flight runtime state has adopted these source edits.

## Dependency handoffs

1. M1 preserves the existing containment milestone and hands M2 a tested mutation/receipt/queue boundary.
2. M2 freezes the shared ledger, coherent envelope, projections, precedence, replay, and transition-authority contracts.
3. M3 adds fenced custody, recurrence, independent verification, canary install, and rollback over M2 contracts.
4. M4 builds the six-hour operational unblocker over M2-M3 without directly mutating plan/chain truth.
5. M5 consumes M4 closed watermarks and histories for read-only daily efficiency analysis and proposal routing.

Every milestone is scoped to roughly one sprint and no more than two weeks. Architecture/public-contract milestones M1-M3 use `partnered-5/full/high @codex`; implementation/product milestones M4-M5 use `partnered-4/full/high @codex`. No milestone requests xhigh/max or reduces robustness below full.

## Launch gates

The chain uses review/manual clean-PR policy and `auto_approve: false`. Before runtime launch, an operator must reconcile these editorial changes with the authoritative active/paused chain workspace and confirm the intended continuation point. Before M2 enforcement and any M3/M4 action canary, the backend/retention, identity/drift, leases, SLOs, allowlist, schedule, promotion, rollback, and ownership decisions in the briefs must be approved. M5 ticket materialization remains report-only until separately approved.

No `megaplan init`, `megaplan chain start`, cloud launch/resume, gate approval, finalize, or execution command is authorized by this handoff.

## Editorial validation evidence

- PyYAML parsing and the repository `ChainSpec` loader passed for `chain.yaml`.
- Top-level North Star declaration, path resolution, required-anchor policy, all five canonical brief paths, profile files, dependency order, human review settings, and canonical initiative directories were checked read-only.
- Eleven focused chain-spec/manual-advancement policy tests passed.
- The broader anchor test module is currently uncollectable because this pre-existing dirty checkout lacks `arnold_pipelines.megaplan.cli.parser`. A wider milestone-validation run otherwise passed 16 tests and exposed one pre-existing auto-merge expectation mismatch; neither issue was caused or repaired by this editorial task.
- No runtime state loader, chain status driver, init/start/resume, cloud command, approval, finalize, or execution path was invoked.
