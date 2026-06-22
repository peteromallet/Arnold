# M7 Merge-Result Conformance

Prove the integrated merge result is the clean-break state after M1-M6 have landed. This is a chain-level release gate, not a legacy implementation sprint.

## Scope

- Build the wheel and sdist from the post-merge checkout.
- Run installed-wheel contract, runtime, CLI, generated-artifact, import-boundary, and deletion conformance checks against the built wheel.
- Run `scripts/chain_done_gate.py` against the chain spec, chain state, plan states, and blocker checklist.
- Run `scripts/m6_purge_gate.py` against the merge-result checkout.
- Re-run generated artifact freshness from the post-deletion tree.
- Verify deleted paths were not resurrected by merge resolution.

## Acceptance

1. Every M1-M6 plan has `current_state == "done"` in its own `state.json`.
2. `completion_contract_mode` and `full_suite_backstop_mode` are enforced, not shadowed.
3. The review blocker checklist has no open items.
4. No shipped product package contains `_pipeline/` or `stages/` legacy runtime directories.
5. `arnold_pipelines.megaplan.pipeline` does not define or export `_build_legacy_pipeline`, `build_legacy_pipeline`, or `compile_planning_pipeline`.
6. Tests do not keep those legacy constructors alive.
7. The installed wheel proves import, CLI, docs, generated artifact, and package metadata behavior from the merge result.
