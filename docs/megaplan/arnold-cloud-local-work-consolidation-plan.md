# Arnold Cloud + Local Work Consolidation Closeout

Date: 2026-07-09

Scope: Arnold-only loose work across the local checkout, Hetzner megaplan cloud
workspace, and GitHub remote branches.

## Final State

The Arnold consolidation was executed to the intended clean end-state.

- The reconciled code/runtime payload is `e6dc24b3c`
  (`Merge Arnold consolidation into main`).
- `origin/main` and `origin/editible-install` are intentionally aligned.
  Follow-up closeout commits recovered two valuable local payloads found during
  final cleanup: `cloud quickstart` and configured-spec worker fallback
  progression. The invariant is that both durable branches point at the same
  commit after each closeout push.
- Local `main` tracks `origin/main`.
- Local `editible-install` tracks `origin/editible-install`.
- The Hetzner cloud checkout `/workspace/arnold` was reset to
  `origin/editible-install` at `e6dc24b3c`.
- The cloud generated-docs check passed after the reset:
  `python scripts/generate_arnold_docs.py --check`.
- All prior remote side branches were removed from GitHub after bundling them
  into a local recovery artifact.
- The primary local checkout was reset to `origin/main`; its previous dirty
  state was archived before cleanup.

## Merge Commit

The reconciled code/runtime payload commit is:

```text
e6dc24b3c Merge Arnold consolidation into main
```

It reconciles the tested consolidation payload into both durable branches:

```text
origin/main
origin/editible-install
```

The commit preserves the `origin/main` and `origin/editible-install` lineages
while landing the cloud runtime, superfixer, extension-reality recovery, and S7
native-parity payload that had previously been split across local/cloud/remote
surfaces.

Final cleanup also recovered local work that was initially present only in the
archived dirty checkout:

- `python -m arnold_pipelines.megaplan cloud quickstart`, matching the existing
  megaplan-cloud skill documentation.
- Multi-sprint North Star preflight/launch guardrails.
- Configured fallback-chain progression for retryable worker failures.

## Verification

Focused verification run before final branch cleanup:

```text
pytest -q tests/cloud/test_repair_contract.py \
  tests/cloud/test_resolver_enforcement.py \
  tests/cloud/test_resolver_enforcement_dispatch.py
# 113 passed

python scripts/generate_arnold_docs.py --check
# Arnold generated artifacts are up to date.

pytest -q tests/arnold_pipelines/megaplan/test_cloud_quickstart.py
# 7 passed

pytest -q tests/arnold_pipelines/megaplan/test_worker_fanout_fallback.py \
  tests/arnold_pipelines/megaplan/test_fallback_observability.py \
  tests/arnold_pipelines/megaplan/test_fallback_chains_characterization.py \
  tests/arnold_pipelines/megaplan/test_auto_native_dispatch.py
# 74 passed

pytest -q tests/cloud/test_watchdog_wrappers.py \
  tests/cloud/test_repair_trigger_wrapper.py \
  tests/cloud/test_meta_repair.py
# 499 passed

pytest -q tests/cloud/test_watchdog_wrappers.py \
  tests/cloud/test_repair_trigger_wrapper.py \
  tests/cloud/test_current_target.py \
  tests/cloud/test_status_snapshot.py \
  tests/cloud/test_meta_repair.py \
  tests/test_chain_completion_guard.py
# 653 passed

pytest -q tests/cloud/test_repair_contract.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/cloud/test_repair_trigger_wrapper.py \
  tests/cloud/test_status_snapshot.py \
  tests/test_chain_completion_guard.py
# 540 passed
```

Cloud post-reset verification:

```text
ssh -o StrictHostKeyChecking=no root@159.69.51.216 \
  "docker exec megaplan-cloud-agent bash -lc \
  'cd /workspace/arnold && git fetch origin && git checkout editible-install && \
   git reset --hard origin/editible-install && git rev-parse --short HEAD && \
   git status --short --branch && python scripts/generate_arnold_docs.py --check'"
```

Observed cloud result:

```text
e6dc24b3c
## editible-install...origin/editible-install
Arnold generated artifacts are up to date.
```

Residual broad-suite note: a larger historical test selection still had
collection/failure issues in older or deleted interfaces. Those failures were
also present in the consolidation tree before this final branch reconciliation
and were not introduced by the cleanup. The green gates above are the focused
runtime/superfixer/consolidation checks used for this landing.

## Local Cleanup Evidence

Before resetting the local checkout, its prior dirty state was preserved under:

```text
/tmp/arnold-final-cleanup-20260709/
```

Important artifacts:

```text
primary-status-before-clean.txt
local-branches-before-clean.txt
worktrees-before-clean.txt
untracked-before-clean.txt
primary-checkout-vs-origin-main.diff
primary-checkout-vs-local-head.diff
primary-untracked-before-clean.tgz
remote-branches-to-clean.txt
remote-branches-unique-logs.txt
remaining-remote-side-branches-20260709.bundle
cloud-stash-codex-temp-superfixer-rebase.patch
```

The old local `main` checkout was patch-equivalent for its lone ahead commit,
but its working tree was not a valid merge source after `origin/main` advanced:
relative to `origin/main` it would have removed many newly landed S7/runtime
files. The correct cleanup action was therefore archive-then-reset, not merge.

## Removed Worktrees

The following local worktrees were clean and removed:

```text
/Users/peteromalley/Documents/Arnold-consolidation-20260709
/Users/peteromalley/Documents/Arnold/.tmp/repair-loop-target-task-fix
```

Earlier temporary worktrees removed during consolidation:

```text
/private/tmp/arnold-custody-fix
/private/tmp/arnold-editible-superfixer
/private/tmp/arnold-main-cherrypick-test
/private/tmp/arnold-main-reconcile-20260709
/Users/peteromalley/Documents/Arnold-consolidation-clean-20260709
```

## Removed Remote Branches

Before deletion, all remaining remote side branches were bundled into:

```text
/tmp/arnold-final-cleanup-20260709/remaining-remote-side-branches-20260709.bundle
```

Deleted remote branches:

```text
checkpoint/cloud-workspace-arnold-20260709
checkpoint/cloud-workspace-arnold-dirty-20260709
checkpoint/s7-native-parity-workspace-20260709
cloud/extension-reality-chain-restart-continuation-backup-20260708
consolidation/arnold-cloud-local-20260709
dev-fix/extension-reality-routing-ledger-removed-plan
dev-fix/f7cbc413-stale-done-chain
fix/chain-custody-guards-min
local/extension-foundation-completion
megaplan/agent-ui-lifecycle-parity/m1
megaplan/canonical-resolver-and-20260707-0108
megaplan/full-lifecycle-parity-20260706-1720
megaplan/m4-evidence-and-drift-gates-20260708-0120
megaplan/progress-auditor-stage-metrics/m1
megaplan/s1-checker-outcomes-builder-20260705-1942
megaplan/s2-5-boundary-evidence-20260706-0521
megaplan/s2-5-boundary-evidence-20260706-0751
megaplan/s2-front-half-native-loop-20260705-2026
megaplan/s3-tiebreaker-and-replan-20260706-2045
megaplan/s4-execute-dag-approval-20260707-0617
megaplan/s5-review-rework-finalize-20260708-0106
megaplan/s6-override-auto-20260708-1014
megaplan/s7-final-conformance-rollout-20260708-1653
recovery/m3-export-readiness-salvage
```

After pruning, the only remote Arnold branches were:

```text
origin/main
origin/editible-install
```

## Archived But Not Landed

The following local loose files were intentionally archived rather than
committed:

- `docs/megaplan/arnold-cloud-local-work-merge-strategy-brief.md`
- `docs/superfixer/**`

Reason: the merge strategy brief and superfixer notes were pre-closeout planning
artifacts. They are recoverable from `primary-untracked-before-clean.tgz`.

The quickstart test was initially archived because the implementation was
missing from the reconciled branch. The final closeout recovered the matching
implementation and restored the test.

The cloud stash `codex-temp-superfixer-rebase` was archived to
`cloud-stash-codex-temp-superfixer-rebase.patch`, then dropped from
`/workspace/arnold`.

## Surviving Branches

The intended surviving shared branches are:

```text
main
editible-install
```

Both should point at the same commit. At code-payload landing time this was
`e6dc24b3c`; after committing this closeout document, both durable branches
should move together to the documentation closeout commit.

## Closeout Criteria

The consolidation is considered closed when these checks remain true:

```text
git status --short --branch
git branch -r
git worktree list --porcelain
ssh -o StrictHostKeyChecking=no root@159.69.51.216 \
  "docker exec megaplan-cloud-agent bash -lc \
  'cd /workspace/arnold && git rev-parse --short HEAD && git status --short --branch'"
```

Expected:

- local `main` clean at `origin/main`;
- local `editible-install` aligned to `origin/editible-install`;
- no extra local worktrees;
- only `origin/main` and `origin/editible-install` remote branches;
- cloud `/workspace/arnold` clean on `editible-install` at the current
  `origin/editible-install` tip.
