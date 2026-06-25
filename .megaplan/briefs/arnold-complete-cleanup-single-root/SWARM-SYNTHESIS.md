# DeepSeek Swarm Synthesis

Ten DeepSeek V4 Pro agents independently reviewed the cleanup plan by component. Their findings are useful, but the plan below applies repo-level judgment rather than copying any one output.

## Strong Convergence

The agents converged on these risks:

- The current canonical package is not yet fully authoritative. Important surfaces still delegate into `arnold.pipelines.megaplan`.
- `_pipeline` is the biggest migration surface. The legacy tree has executor, registry, run CLI, resume, preflight, dispatch, patterns, builder, hooks, and test coverage that cannot be deleted before equivalent canonical responsibility modules exist.
- Import-time side effects are load-bearing: content-type registration, model adapter installation, native normalizer registration, and public lazy exports need import-order characterization before any shim or deletion.
- CLI, chain, resume, PR helper, and worker subprocess paths need explicit parity gates. A green local import test is not enough.
- Packaging is a trap: editable installs can see `arnold/pipelines/megaplan`, while wheels exclude it. Discovery rows and builder paths must resolve inside shipped canonical packages.
- Temporary shims need a machine-readable registry and a shrink-only ratchet. Otherwise the "temporary" state becomes the architecture.
- Skills and docs are execution surfaces for agents. Stale `python -m arnold.pipelines.megaplan` examples are not harmless docs debt.
- Runtime process isolation must not regress while import roots move. Engine-root detection, worker env, and Hermes/vendored runtime import paths need batch validation.
- Remaining external loose work should be decided separately: archive the old TypeScript Arnold snapshot, keep active Reigh worktrees only while their processes live, and delete operational checkouts afterward.

## My Judgment

The previous single-root ticket was directionally correct but underspecified in two places:

1. It did not make `_pipeline` extraction a first-class milestone.
2. It treated "temporary shims" as implementation scaffolding without first freezing a strict shim registry and import-order contract.

The safe direction is stricter:

- Final state has no `_pipeline` namespace in either root.
- Extract `_pipeline` responsibilities into named canonical modules.
- Migrate tests and callers to those modules.
- Only then delete or intentionally fail the legacy import path.
- No permanent shim, and no shim to a missing target.

## Resulting Epic Shape

This prep splits the work into seven sprint-sized milestones:

1. Close remaining loose-work decisions and freeze the baseline.
2. Inventory all legacy callers/surfaces and add ratchets.
3. Make canonical imports and side effects deterministic.
4. Extract `_pipeline` and runtime responsibilities into canonical modules.
5. Prove CLI, chain, resume, worker, discovery, docs, and wheel parity.
6. Delete the legacy root and purge stale generated/source artifacts.
7. Run merge-result conformance and close external cleanup exceptions.
