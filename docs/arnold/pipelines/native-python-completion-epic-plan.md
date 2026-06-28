# Native Python Completion Epic Plan

## End-State And Why This Is Split

Top-level North Star from `briefs/native-python-pipelines-completion/NORTHSTAR.md`:

> Arnold runs entirely on native Python pipelines. Every package builds native declarations and returns projected `Pipeline` compatibility shells through `Pipeline.native_program`. Execution, resume, and testing use native runtime semantics and native traces as truth. Graph-era surfaces are removed or explicitly shimmed only after import inventory proves it is safe.

This stays the durable destination. The work is split into three epics because the V4 plan's dependency graph already falls into three dependency-closed stages rather than one uniform chain:

- foundation and path normalization (`M1 -> M2`)
- package/runtime migrations (`M3 -> M3.5 -> M4`)
- verification, docs, and destructive cleanup (`M5 -> M6 -> M7`)

This keeps each epic internally coherent, gives each one a concrete handoff artifact to the next epic, and avoids mixing contract transition, behavior-heavy migrations, and final purge in a single long-running chain.

## Epic 1: Platform Contract And Layout Foundation

Purpose: establish the native-first platform contract and normalize Megaplan-owned package paths before any broad package migrations begin.

Epic North Star: Arnold's platform surfaces accept projected shells with `Pipeline.native_program`, native runtime is the preferred execution path, and the Megaplan package names/layout used by downstream migrations are stable.

Ordered milestones:

| Milestone | One-line purpose | Rubric |
| --- | --- | --- |
| `M1 - Platform contract transition` | Add `Pipeline.native_program`, make executor/registry/validator/discovery/CLI native-first, and keep bundle/flag compatibility shims during the transition. | `partnered-5 / thorough / high` |
| `M2 - Megaplan subpipelines layout normalization` | Normalize `writing_panel_strict` and `select_tournament` into stable package paths before behavior-heavy migrations. | `partnered-5 / thorough / high` |

Tiering decision: carry over the current chain's rubric unchanged. `M2` is more mechanical than the other milestones, but it is still import-topology-sensitive and is a direct prerequisite for `M3`; the existing `partnered-5` setting is conservative and defensible.

Base branch and branch strategy:

- Create `native-python-working-tree` from the current editable branch `editible-install`.
- Reconcile donor work from `native-python-pipelines` onto `native-python-working-tree` before launch; do not run Epic 1 from the donor branch directly.
- Run Epic 1 on `native-python-working-tree` with review-gated merges, then keep Epic 1's green tip as the starting point for Epic 2.

Handoff to Epic 2:

- `Pipeline.native_program` exists on projected shells and is preferred by executor/runner/CLI/registry/validator.
- Manifest-first discovery and native runtime default behavior are in place, with transitional compatibility shims still available.
- `writing_panel_strict` and `select_tournament` have normalized canonical package paths that `M3` can migrate without further path churn.

## Epic 2: Package And Runtime Migrations

Purpose: migrate the package set that is closest to the final contract, then migrate canonical Megaplan and `evidence_pack` onto the shared native execution and resume model.

Epic North Star: every package in scope for the migration returns a projected shell with `native_program`, canonical Megaplan runs through native runtime semantics instead of stage-order/bundle heuristics, and `evidence_pack` uses the shared native resume contract.

Ordered milestones:

| Milestone | One-line purpose | Rubric |
| --- | --- | --- |
| `M3 - Root and shared package migrations` | Migrate `creative`, `doc`, `jokes`, `live_supervisor`, `writing_panel_strict`, `epic_blitz`, `select_tournament`, `folder_audit`, and `deliberation` to the final package contract. | `partnered-5 / thorough / high` |
| `M3.5 - Canonical Megaplan migration` | Migrate canonical `megaplan`, `native_runner.py`, and `auto.py` off stage-order and bundle-carried execution heuristics. | `partnered-5 / extreme / max` |
| `M4 - Evidence pack native migration` | Move `evidence_pack` to the same native execution and shared resume semantics used everywhere else. | `partnered-5 / extreme / max` |

Tiering decision: carry over the current chain's rubric unchanged. `M3.5` and `M4` remain the highest-intensity milestones because they touch flagship runtime/resume behavior and can fail semantically while still looking structurally correct.

Base branch and branch strategy:

- Start Epic 2 from the completed tip of Epic 1 on `native-python-working-tree`.
- Keep the same long-lived integration branch so the runtime substrate, package moves, and migrated package set stay in one auditable line of history.
- If operators want per-epic PRs, cut the Epic 2 branch from the Epic 1-complete tip, but keep `native-python-working-tree` as the declared base branch in the chain spec.

Handoff to Epic 3:

- The migrated package set is validator-clean under the `M1` contract.
- Canonical Megaplan runs via `native_program` and no longer depends on stage-order routing shortcuts as the primary path.
- `evidence_pack` uses shared native suspension/resume semantics, which makes native traces and native-owned goldens safe to treat as truth in `M5`.

## Epic 3: Verification, Docs, And Final Purge

Purpose: convert tests and goldens to native truth, make docs/scaffolds native-first, then perform the import-inventory-driven relocation and purge.

Epic North Star: native traces are the canonical test oracle, docs and scaffolds only teach the native-first contract, and graph-era surfaces are removed or intentionally shimmed only after the final import inventory proves what is still live.

Ordered milestones:

| Milestone | One-line purpose | Rubric |
| --- | --- | --- |
| `M5 - Native test and golden-trace cleanup` | Rewrite or delete every named old-contract parity/baseline suite so native truth and native-owned goldens become canonical. | `partnered-5 / thorough / high` |
| `M6 - Docs and scaffolds native-first` | Remove graph-first and shim-based guidance from docs, generated docs, authoring helpers, and templates. | `partnered-5 / thorough / high` |
| `M7 - Megaplan relocation and final purge` | Produce the final import inventory, relocate any still-live `_pipeline/` ownership, and delete legacy surfaces only where the inventory proves it is safe. | `partnered-5 / extreme / max` |

Tiering decision: carry over the current chain's rubric unchanged. `M6` is mostly corrective, but keeping its current setting is reasonable because it must match the real post-`M5` code and generated docs exactly; `M7` remains extreme because it is the destructive purge milestone.

Base branch and branch strategy:

- Start Epic 3 from the completed tip of Epic 2 on `native-python-working-tree`.
- Do not launch `M7` until `M5` and `M6` are green on that same branch; the purge depends on code, tests, docs, and scaffolds already reflecting the native-first truth.
- Merge `native-python-working-tree` back into `editible-install` only after Epic 3 completes and the final inventory-backed cleanup is verified.

Handoff / final deliverables:

- Native-truth suites and native-owned golden traces are the default test oracle.
- Docs, templates, and authoring helpers teach only the native-first package contract for new work.
- `docs/arnold/pipelines/migration-final-import-inventory.md` records the final decision log for retained shims vs deleted graph-era surfaces.

## Epic Dependency And Ordering

The epics must run strictly in this order:

1. Epic 1 -> Epic 2
   `M3` depends on `M1` and `M2`, and `M3.5` depends on `M1`, `M2`, and `M3`. Epic 2 therefore cannot start until the platform contract and normalized package paths from Epic 1 are complete.
2. Epic 2 -> Epic 3
   `M5` depends on `M3`, `M3.5`, and `M4`. Epic 3 therefore cannot start until the migrated package set, canonical Megaplan runtime, and `evidence_pack` resume contract from Epic 2 are complete.

There is no clean parallel split under the V4 dependency graph. The natural handoffs are sequential and artifact-driven.

## Readiness / Launch Prep For Epic 1

Before Epic 1 launches, reconcile the readiness caveats into a concrete launch surface:

1. Start from the real editable base.
   Create `native-python-working-tree` from `editible-install`, not from `main` and not from an older cleanup branch.
2. Reconcile the donor branch intentionally.
   Port the committed plan/brief artifacts and the native-runtime code shapes from `native-python-pipelines` onto `native-python-working-tree`, including the substrate called out in the readiness note: `arnold/pipeline/native/compiler.py`, canonical Megaplan runtime files, and `arnold/pipelines/evidence_pack/**`.
3. Commit epic inputs as source, not ignored scratch state.
   The split-epic specs, the top-level North Star, and the milestone briefs must live as committed files on `native-python-working-tree`; do not rely on an ignored local `chain.yaml`, and do not carry forward generated `.megaplan/plans/.chains/*` state as source input.
4. Fix base-branch and anchor metadata in each new epic spec.
   Each split chain spec should declare `base_branch: native-python-working-tree` and `anchors.north_star` pointing at the committed North Star document so `chain start` validates against the real launch branch and durable destination.
5. Preserve review gates for the risky migration stages.
   Keep `merge_policy: review`, `driver.auto_approve: false`, and `driver.require_clean_base: true` for the launch shape. The readiness note is explicit that auto-merge / auto-approve is too aggressive until the risky runtime milestones are proven.
6. Validate the Epic 1 spec before launch.
   From `native-python-working-tree`, run `chain status` against the new Epic 1 spec, confirm every `idea:` path exists, and launch with `--one` first so the platform-contract handoff can be reviewed before the next epic is prepared.

## Epic 1 `chain.yaml` Skeleton

This is the launch-ready shape in principle for the first split epic. It is intentionally a skeleton only; this document does not modify any live chain spec.

```yaml
base_branch: native-python-working-tree

anchors:
  north_star: briefs/native-python-pipelines-completion/NORTHSTAR.md

milestones:
  - label: m1-platform-contract
    idea: briefs/native-python-pipelines-completion/m1-platform-contract.md
    profile: partnered-5
    robustness: thorough
    depth: high

  - label: m2-megaplan-subpipelines-layout
    idea: briefs/native-python-pipelines-completion/m2-megaplan-subpipelines-layout.md
    profile: partnered-5
    robustness: thorough
    depth: high
    depends_on: [m1-platform-contract]

on_failure:
  retry_same_milestone: once
  then: escalate_with_artifacts
  abort: stop_chain

on_escalate:
  preserve_worktree: true
  require_status_summary: true
  abort: stop_chain

merge_policy: review

driver:
  auto_approve: false
  require_clean_base: true
  robustness: thorough
  poll_sleep: 8.0
```

## Summary

This plan keeps the exact same eight milestones and the same V4 dependency graph, but repackages them into three epics that each have a clear theme and handoff:

- Epic 1 (`M1-M2`): contract and layout foundation
- Epic 2 (`M3-M4`, including `M3.5`): package and runtime migration
- Epic 3 (`M5-M7`): verification, docs, and final purge

That is the smallest split that preserves the real dependency closures from V4 while making the first epic genuinely launchable on `native-python-working-tree`.
