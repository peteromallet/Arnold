# AgentBox, cloud workspace, runtime, and Codespaces inventory

Snapshot taken 2026-07-14 13:22:28 UTC (+00:00). This is a read-only inventory and deletion proposal. No branch, ref, stash, worktree, clone, cloud workspace, volume, Codespace, process, or file payload was deleted or modified while gathering it. Authenticated remote URLs were inspected only to classify repositories; credential-bearing URL values are intentionally omitted.

## Classification vocabulary

- **KEEP — active/protected**: currently owns a live process, paused durable plan, canonical integration, or runtime source.
- **KEEP — land first**: contains a named useful unit that is not yet proven landed. Preserve it until the named commit/blob or cross-repository work is landed and verified; it then becomes **READY-DELETE**.
- **READY-DELETE**: positive evidence shows the payload is remote-contained, duplicated, superseded, or generated residue. This is only a recommendation for explicit user approval. Nothing was deleted.

## Coverage and control-plane findings

An exhaustive `/workspace` search for Git directories and linked-worktree `.git` files, excluding dependency/cache trees, found 95 Git workspaces at the final snapshot. The count increased from the initial 93 because the consolidation owner created the isolated integration and WBC verification worktrees during the survey. Of the initial 93, 84 were Arnold repositories or Arnold runtime mirrors and 9 were other product repositories.

The current tmux sessions were `agent`, `heartbeat`, `megaplan-resident-discord`, and `watchdog`. The watchdog report timestamped `2026-07-14T12:21:47.581336+00:00` classified:

- alive: `agent-edit-verifiable-transaction-spine`, `repository-strategy-roadmap`;
- paused: `discord-resident-lifecycle-corrective-20260710`, `megaplan-maintenance`;
- complete: `agent-edit-canonical-deltas`, `canonical-run-state-control-plane`, `extension-foundation-completion`, `extension-reality-clean-lane-recovery`, `megaplan-chain-reigh-extension-composition-spine-epic-12d49a3e`, `megaplan-native-parity-corrective`, `megaplan-north-star-sense-checks-revise-design`, `native-composition-followup`, `progress-auditor-stage-metrics`, `runauthority-epic-cloud`, `superfixer-alive-but-failed-recovery`, and `workflow-boundary-contracts-corrective-20260710`;
- supervisor source: both `sync_dirty` and `synced` observations were present for `editable-install`.

At the process observation point, the agent-edit chain had PID 4053054 and a log advancing through 2026-07-14 12:53:03 UTC (+00:00); repository-strategy-roadmap had PID 3320315 and a log advancing through 2026-07-14 12:53:01 UTC (+00:00). A later observation showed the repair wrapper for agent-edit still active. These workspaces must not be disturbed.

## Runtime and editable-install provenance

Before activation work, the resident was PID 470721, started 2026-07-14 11:57:16 UTC (+00:00), with:

- cwd `/workspace/arnold`;
- executable `/root/.pyenv/versions/3.11.11/bin/python3.11`;
- `MEGAPLAN_RUNTIME_SRC=/workspace/arnold`;
- `MEGAPLAN_RESIDENT_STORE_ROOT=/workspace/arnold/.megaplan/resident`;
- `MEGAPLAN_RESIDENT_MODE=production`;
- `PYTHONPATH=/workspace/arnold:`.

The resident source revision supplied by the immutable envelope and confirmed at survey start was `612b139971e1a65d2a40f9e387a5e8ff3e2ab960`.

Ordinary Python imports resolved to `/workspace/arnold/arnold_pipelines/__init__.py` and `/workspace/arnold/arnold_pipelines/megaplan/__init__.py`, but only because cwd/`PYTHONPATH` took precedence. Installed distribution metadata reported `arnold 0.23.0`, while `_editable_impl_arnold.pth` pointed to `/workspace/workflow-boundary-contracts-corrective-20260710/Arnold/.megaplan/runtime/editable-engine`, whose Git revision was `91a33dab28f3`. Thus import-path provenance and editable-distribution provenance disagreed. Both must be repointed to a clean checkout of the exact landed `origin/main` SHA, and the resident must be canonically restarted and re-proven before activation can be claimed.

Thirteen cloud session markers explicitly declared `editable_source_branch=editible-install`:

1. `agent-edit-canonical-deltas`
2. `canonical-run-state-control-plane`
3. `discord-resident-lifecycle-corrective-20260710`
4. `extension-foundation-completion`
5. `extension-reality-clean-lane-recovery`
6. `megaplan-chain-reigh-extension-composition-spine-epic-12d49a3e`
7. `megaplan-maintenance`
8. `megaplan-north-star-sense-checks-revise-design`
9. `native-composition-followup`
10. `repository-strategy-roadmap`
11. `runauthority-epic-cloud`
12. `superfixer-alive-but-failed-recovery`
13. `workflow-boundary-contracts-corrective-20260710`

Their exact control records are `/workspace/.megaplan/cloud-sessions/<session>.json`. The active repository-strategy-roadmap chain genuinely started with `REF=editible-install`, so its primary, mirror, and supervisor source remain protected even after the canonical resident is repointed.

## KEEP — active/protected

| Exact path | Contents and positive evidence | What would be lost / rationale |
|---|---|---|
| `/workspace/arnold` | Canonical resident/runtime source; dirty user checkout initially at `612b139971e1`; resident cwd and `MEGAPLAN_RUNTIME_SRC` both point here. | Deleting or changing it would destroy current user work and the live runtime source. Keep permanently as the canonical checkout. |
| `/workspace/arnold-consolidation-20260714` | Isolated consolidation branch `consolidate/arnold-runtime-activation-20260714`; active synthesis worktree. | Would lose the in-flight integration and its durable handoff evidence. Keep until canonical main landing and archival are complete. |
| `/workspace/arnold-wbc-source-verify` | Clean detached verification worktree at exact WBC tip `cbe69337d6f4`. | Would remove the independent source-verification surface during integration. Keep through merge verification; then it becomes ready. |
| `/workspace/agent-edit-verifiable-transaction-spine/vibecomfy` | Active VibeComfy chain, branch `megaplan/agent-edit-verifiable-transaction-spine/sprint-2`, SHA `627eb75aab5f`; live chain/repair ownership. | Would interrupt an active chain. Keep until that chain reaches its own terminal state. |
| `/workspace/agent-edit-verifiable-transaction-spine/vibecomfy/.megaplan/runtime/editable-engine` | Clean Arnold runtime mirror at `7644f55dd9be`, owned by the active agent-edit chain. | Would break the active chain's pinned engine. Keep with its owner. |
| `/workspace/repository-strategy-roadmap/Arnold` | Active chain, branch `megaplan/repository-strategy-roadmap/m4-migration-compatibility`, SHA `3f47ff596fad`; session explicitly started from `editible-install`. | Would interrupt the active migration chain. Keep until terminal completion. |
| `/workspace/repository-strategy-roadmap/Arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror at `91a33dab28f3`, used by the active roadmap chain. | Would break the active chain's runtime. Keep with its owner. |
| `/workspace/.megaplan/repository-strategy-roadmap-supervisor-source` | Branch `editible-install`, SHA `405eb641b0d4`; watchdog supervisor source with three dirty generated/composed skill documents. | It is the live supervisor/watchdog source. Keep until the active chain and supervisor migration finish. |
| `/workspace/discord-resident-lifecycle-corrective-20260710/Arnold` | Watchdog status `paused`; 48 tracked and 27 untracked paths containing source/docs and durable paused-plan state. | A paused plan is protected, not abandoned. Keep until explicit resume and terminal disposition. |
| `/workspace/megaplan-maintenance/Arnold` | Watchdog status `paused`; 57 tracked and 16 untracked paths containing source/docs and durable paused-plan state. | A paused plan is protected. Keep until explicit resume and terminal disposition. |
| `/workspace/.megaplan` | Live cloud-session markers, watchdog control data, supervisor runtimes, and control-plane evidence. | Deletion would remove current process custody and durable operational evidence. Keep. |
| `/workspace/kimi-goal-operator` | Live repair/operator artifacts; a repair wrapper was active at the final process observation. | Deletion would remove active repair custody/evidence. Keep. |
| `/workspace/ops` | Current consolidation/operator evidence directory. | Keep through completion and evidence archival. |

Credential files, hot-environment files, watchdog/auditor reports and logs, backup/recovery/checkpoint directories, and `/workspace/.megaplan` volumes are likewise protected. Several authenticated Git remote URLs embed a credential; the secret is not reproduced here and should be rotated separately.

## KEEP — land or reconcile first, then READY-DELETE

| Exact path | Useful payload and required proof | What would be lost / rationale |
|---|---|---|
| `/workspace/workflow-boundary-contracts-corrective-20260710/Arnold` | Clean completed WBC branch `megaplan/s4-consumption-and-general-20260714-0128` at `cbe69337d6f4`, remote-contained. | Keep until WBC is proven in canonical main; then only an already-landed clean clone would be lost. |
| `/workspace/workflow-boundary-contracts-corrective-20260710/Arnold/.megaplan/runtime/editable-engine` | Clean detached `91a33dab28f3`; pre-activation pip `.pth` target. | Keep until pip metadata is repointed and proven; then it is an obsolete runtime mirror. |
| `/workspace/arnold/.megaplan/tmp-superfixer-learning` | Unique untracked `arnold_pipelines/megaplan/cloud/superfixer_episodes.py` blob `db06c21` and `tests/cloud/test_superfixer_episodes.py` blob `312254a`; 0/2 matched any other workspace and neither was present in object history. | Deleting before landing loses the only bounded-superfixer-learning implementation and tests. Land and byte-verify both blobs; then ready. |
| `/workspace/arnold-chain-guard-fix` | Four dirty source/test blobs exactly match checkpoint commit `0db05edc66ff` in the next row. | Keep until the checkpoint unit is landed; after that only duplicate working copies/ledger residue would be lost. |
| `/workspace/arnold-cloud-dirty-checkpoint-20260709` | Local checkpoint branch at `0db05edc66ff`; exact preservation of all four chain-guard source/test blobs. | Deleting before landing loses the local checkpoint commit. Land it, then ready. |
| `/workspace/arnold-chain-guard-min` | Clean local-only commit `e4592338c628`, `fix/chain-custody-guards-min`. | Deleting before its verdict loses a local-only focused chain-guard commit. Land or prove superseded, then ready. |
| `/workspace/arnold-gate-contract-audit-final` | Clean local-only final gate-contract commit `94abc498ec73`. | Deleting before landing loses local-only schema-derived gate work. Land/reconcile with its predecessor, then ready. |
| `/workspace/arnold-gate-contract-audit` | Clean local-only predecessor `790fa2583861`. | Preserve until the final gate unit is landed and ancestry/supersession is proven; then ready. |
| `/workspace/arnold/.megaplan/tx-spine-systemic-fix` | Clean local-only tip `9c3bb63ece9b`; named transaction-projection series `3221870`, `e5f247b`, `0a31d53`, `9c3bb63`. | Deleting before landing loses the local transaction-spine event-projection series. Land/reconcile the series, then ready. |
| `/workspace/context-router-latest-machine-capture` | Clean local-only structured-capture commit `e8143ebccfe7`. | Deleting before landing loses the only named structured-capture commit. Land or prove superseded, then ready. |
| `/workspace/legacy-editible-durable-reconcile-20260713` | Clean local-only legacy checkpoint `a8d417c09032`. | Preserve until the consolidation owner lands it or positively proves all blobs superseded; then ready. |
| `/workspace/extension-foundation-completion/reigh-app-extension-foundation-finish` | Clean local-only Reigh commit `54ef91ddaa2e`; upstream is wrong/severely diverged. | This is useful work in another repository. Push/land it on the correct Reigh branch; then ready. Never merge it into Arnold. |
| `/workspace/extension-foundation-completion/reigh-app` | Reigh epic branch `epic/extension-foundation-completion`, SHA `b7abdf5d3f7b`, with 2 tracked/5 untracked paths. | Preserve and land in Reigh; then ready. |
| `/workspace/reigh-extension-composition-spine-epic-12d49a3e/reigh-app` | Reigh branch with unpushed commit `6e2b3284e8f3`, 10 tracked/2 untracked paths, and a 25-file stash (`+2323/-90`). | Deleting would lose unpushed Reigh implementation and stash. Reconcile/push in Reigh; then ready. |

## READY-DELETE — clean remote-contained checkouts and runtime mirrors

For every row below, `git status` was clean at the snapshot unless a specific generated-only exception is stated, and the HEAD was contained by at least one remote ref or duplicated by an exact SHA elsewhere. What would be lost is only the redundant checkout plus ignored caches/build artifacts; the commits remain reachable remotely or in another named clone.

| Exact path | Contents / evidence and rationale |
|---|---|
| `/workspace/.codex-worktrees/superfixer-safe-path-20260714` | Clean Arnold worktree `09c440d2a3a4`; remote-contained. |
| `/workspace/agent-edit-canonical-deltas/vibecomfy` | Completed VibeComfy chain, clean `0f0b27fd2556`; remote-contained. |
| `/workspace/agent-edit-canonical-deltas/vibecomfy/.megaplan/runtime/editable-engine` | Clean Arnold mirror `3780bf522c59`; remote-contained. |
| `/workspace/app` | Clean non-Arnold app checkout `d7d90a784dc1`; contained by three remote refs. |
| `/workspace/arnold-baseline-check` | Clean detached Arnold baseline `17fb30d3a2a2`; contained by eight remote refs. |
| `/workspace/arnold-editible-pre-bf51994fd-checkpoint` | Clean checkpoint `22aaffbb2579`; contained by twenty remote refs. |
| `/workspace/arnold-meta-repair-fallback` | Clean detached `0f6639785503`; remote-contained. |
| `/workspace/arnold-quality-gate` | Clean branch `quality-gate-stale-deviations` at `e7bb38b581b2`; remote-contained. |
| `/workspace/arnold-roadmap-superfix` | Clean branch `fix/repository-strategy-roadmap-launch-custody` at `c15adac3775d`; remote-contained. |
| `/workspace/arnold-terminal-audit` | Clean `terminal-audit-no-model` at `b59f98beb8f9`; remote-contained. |
| `/workspace/arnold/.git/worktrees-tmp/repair-push` | Clean detached `b401920fd0a4`; remote-contained. |
| `/workspace/arnold/.megaplan/tmp-push-watchdog-fix` | Clean `editible-install` at `d6962a1d0783`; remote-contained. |
| `/workspace/arnold/.megaplan/tmp-roadmap-superfix/fix-worktree` | Clean `fix/repository-strategy-roadmap-runtime-isolation` at `991756694ad7`; remote-contained. |
| `/workspace/arnold/.megaplan/tmp-superfixer-agent-edit/fix-worktree` | Clean repair worktree at `405eb641b0d4`; remote-contained and duplicated by the live supervisor source. |
| `/workspace/arnold/.megaplan/tmp-superfixer-wbc/custody-reconcile` | Clean detached `d63a4de568b5`; remote-contained. |
| `/workspace/canonical-run-state-control-plane/arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `81f9d7474039`; remote-contained. |
| `/workspace/custody-control-plane-240c2cca/arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `35814319d8a2`; remote-contained. |
| `/workspace/discord-resident-lifecycle-corrective-20260710/Arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `7fe6fef0f4bc`; remote-contained. The paused primary remains protected. |
| `/workspace/discord-resident-lifecycle-launch-20260710` | Clean launch checkout `7fe6fef0f4bc`; contained by nine remote refs. |
| `/workspace/extension-foundation-completion/reigh-app/.megaplan/runtime/editable-engine` | Arnold mirror at `b7bef4a7449c`; only dirty path is a stale/generated native-parity `chain.yaml`; canonical copies exist elsewhere. |
| `/workspace/extension-reality-chain-restart-continuation/arnold/.megaplan/runtime/editable-engine` | Clean Arnold mirror `d6962a1d0783`; remote-contained. |
| `/workspace/extension-reality-clean-lane-recovery/arnold/.megaplan/runtime/editable-engine` | Clean Arnold mirror `ed529ba0489a`; remote-contained. |
| `/workspace/extension-reality-clean-lane-recovery/arnold/.megaplan/worker_tmp/clean-lane` | Clean validation worktree `5af4ba182f17`; remote-contained. |
| `/workspace/extension-reality-clean-lane-recovery/arnold/.megaplan/worker_tmp/product-proof` | Clean validation worktree `dfe60989d794`; remote-contained. |
| `/workspace/extension-reality-convergence-epic/reigh-app/.megaplan/runtime/editable-engine` | Clean Arnold mirror `5ae18b5fd9c9`; remote-contained. |
| `/workspace/extension-reality-m3-m4-recovery` | Clean recovery checkout `8b2dbda268e4`; remote-contained. |
| `/workspace/megaplan-maintenance/Arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `7fe6fef0f4bc`; remote-contained. The paused primary remains protected. |
| `/workspace/megaplan-north-star-sense-checks-revise-design/arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `3f266ec491d9`; remote-contained. |
| `/workspace/native-python-pipelines-completion-parent-22937539/arnold/.megaplan/runtime/editable-engine` | Arnold mirror `65e55424c538`; only dirty path is stale/generated native-parity `chain.yaml`; HEAD remote-contained. |
| `/workspace/progress-auditor-stage-metrics/Arnold/.megaplan/runtime/editable-engine` | Arnold mirror `b499b1f26a2e`; only dirty path is stale/generated native-parity `chain.yaml`; HEAD remote-contained. |
| `/workspace/reigh-extension-composition-spine-epic-12d49a3e/reigh-app/.megaplan/runtime/editable-engine` | Clean Arnold mirror `c663821ebfdf`; remote-contained. The Reigh primary remains KEEP-land-first. |
| `/workspace/resonance-full-reconcile-20260713` | Clean integration checkout `7558ce9c7da5`; contained by eight remote refs. |
| `/workspace/runauthority-epic-cloud/Arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `7fe6fef0f4bc`; remote-contained. |
| `/workspace/runauthority-epic-d58c26ea/arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `7fe6fef0f4bc`; remote-contained. |
| `/workspace/runauthority-epic-engine-fix` | Clean `editible-install` checkout `45cd38bd2458`; remote-contained. |
| `/workspace/runauthority-epic/Arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `17885a41f1c3`; remote-contained. |
| `/workspace/runauthority-sprint-1/Arnold/.megaplan/runtime/editable-engine` | Clean detached Arnold mirror `3139b2c154ad`; remote-contained. |
| `/workspace/sequential-model-fallbacks/Arnold/.megaplan/runtime/editable-engine` | Arnold mirror `d1412d378f30`; only dirty path is stale/generated native-parity `chain.yaml`; HEAD remote-contained. |
| `/workspace/superfixer-alive-but-failed-recovery/Arnold/.megaplan/runtime/editable-engine` | Arnold mirror `5694e35f71dd`; only dirty path is stale/generated native-parity `chain.yaml`; HEAD remote-contained. |
| `/workspace/vibecomfy-trust-corrective-2026-07/vibecomfy` | Clean VibeComfy corrective branch `e3e46c0fe0e5`; remote-contained. |
| `/workspace/vibecomfy-trust-corrective-2026-07/vibecomfy/.megaplan/runtime/editable-engine` | Clean Arnold mirror `7fe6fef0f4bc`; remote-contained. |
| `/workspace/vibecomfy-trust-correctness-2026-07/vibecomfy` | Clean VibeComfy main `e3e46c0fe0e5`; remote-contained. |
| `/workspace/vibecomfy-trust-correctness-2026-07/vibecomfy/.megaplan/runtime/editable-engine` | Clean Arnold mirror `b59f98beb8f9`; exact SHA exists in other Arnold clones even though this mirror has no containing local remote ref. |
| `/workspace/wbc-editible-ra-integration` | Clean integration checkout `4291bf630efc`; remote-contained. |
| `/workspace/withings-health-integration/Pumpernickel` | Clean non-Arnold checkout `ec50dde3cd54`; remote-contained. |

## READY-DELETE — superseded, patch-equivalent, or generated residue

| Exact path | Contents and positive evidence | What would be lost / rationale |
|---|---|---|
| `/workspace/arnold-editible-install` | 193 staged paths: 109 modified, 84 deleted, 0 added. All 109 modified working blobs exactly matched blobs in other Arnold workspaces; the rest represented absence. HEAD `4291bf630efc` is remote-contained. | Only a redundant old-tree synthesis and deletions would be lost; no unique file payload. |
| `/workspace/arnold/.megaplan/audit-resume-precedence` | Eight source/test blobs were exact duplicates in WBC/current/runauthority trees. | Only a duplicate repair-resume experiment and one untracked duplicate would be lost. |
| `/workspace/arnold/.megaplan/tmp-superfixer-wbc/fix-worktree` | All 12 dirty skill/composed-document blobs exactly matched other preserved trees. | Only a failed/intermediate WBC repair worktree would be lost. |
| `/workspace/wbc-c1-root-corrective-20260711` | Final WBC `cbe69337d6f4` contains exact equivalents for 273/273 nonblank additions in `boundary_contracts.py`, 143/143 boundary-contract test additions, and 81/81 semantic-test additions. Newer trees also contain `durable_repair_active` and `projection_degraded`. | Only an intermediate corrective attempt and generated residue would be lost. |
| `/workspace/progress-auditor-stage-metrics/Arnold` | Watchdog marks complete. The only non-ledger source change, `status_view.py`, exactly duplicates code introduced by commit `c6eb025`, an ancestor of both main and WBC; remaining dirt is generated ledger/log data. | Historical run telemetry and duplicate source only. |
| `/workspace/context-router-machine-capture` | `git cherry origin/main` reports `-` for `db615eb2ee54`, proving patch equivalence. | Only a patch-equivalent detached checkout. |
| `/workspace/prompt-fix-machine-capture` | `git cherry origin/main` reports `-` for `d4340acdb2d9`; adjacent bundle is byte-equivalent preservation. | Only a patch-equivalent detached checkout/bundle copy. |
| `/workspace/prompt-fix-final-reconcile` | `git cherry origin/main` reports `-` for `adcd131052ed`; exact bundle preservation exists. | Only a patch-equivalent detached checkout/bundle copy. |
| `/workspace/extension-reality-final-verify` | Dirty paths are generated Playwright `test-results` traces and last-run state; HEAD is remote-contained. | Only reproducible test traces/results. |
| `/workspace/canonical-run-state-control-plane/arnold` | Watchdog marks complete; all 16 tracked and one untracked paths are generated incident-ledger projections. | Historical generated incident telemetry only; source commit remains remote. |
| `/workspace/custody-control-plane-240c2cca/arnold` | Completed/dormant parent; dirty paths are generated incident-ledger projections. | Historical generated telemetry only. |
| `/workspace/extension-reality-clean-lane-recovery/arnold` | Watchdog marks complete; two dirty paths are generated run/ledger state. | Historical generated telemetry only. |
| `/workspace/megaplan-north-star-sense-checks-revise-design/arnold` | Watchdog marks complete; three dirty paths are generated ledger/projection state. | Historical generated telemetry only. |
| `/workspace/runauthority-sprint-1/Arnold` | Completed/dormant parent; dirty paths are generated ledger/projection state. | Historical generated telemetry only. |
| `/workspace/superfixer-alive-but-failed-recovery/Arnold` | Watchdog marks complete; dirty paths are generated ledger/projection state. | Historical generated telemetry only. |
| `/workspace/runauthority-epic-d58c26ea/arnold` | Completed/dormant parent; two dirty paths are generated ledger state. | Historical generated telemetry only. |
| `/workspace/runauthority-epic-cloud/Arnold` | Watchdog marks complete. Old completion-manifest/proof-map hashes (`301e76`, `da5caf`) are superseded by WBC dependency-completion-proof hashes (`e53b1cc`, `ef764cd`); remaining dirt is ledger/output data. | Obsolete proof artifacts and historical telemetry only. |
| `/workspace/runauthority-epic-all-codex/Arnold` | Only dirty path is historical `cloud.yaml`; branch HEAD is remote-contained. | Obsolete launch configuration only. |
| `/workspace/runauthority-epic/Arnold` | Dirty source-independent paths are incident-ledger projections and initiative handoff output; implementation HEAD is remote-contained. | Historical generated telemetry/handoff copies only. |
| `/workspace/extension-reality-chain-restart-continuation/arnold` | Clean remote-contained branch; archived/cancelled repair attempt owns the stash described below. | Only completed/cancelled chain checkout after stash approval. |
| `/workspace/extension-reality-chain-restart-continuation/arnold/.worktrees/fix-chain-custody-guards-min` | Clean linked worktree, remote-contained; shares the same archived repair stash. | Only redundant linked checkout after stash approval. |
| `/workspace/extension-reality-convergence-epic/reigh-app` | Remote-contained Reigh HEAD; untracked paths are generated outcome and telemetry files. No live owner was found. | Historical outcome/telemetry only. |
| `/workspace/megaplan-native-parity-corrective/Arnold` | Watchdog marks complete; remote final branch contains `d920ff0`. Blob analysis found 73/74 non-ledger dirty files duplicated elsewhere; the sole unmatched file was an older runauthority chain config. | Failed/intermediate retry state, historical telemetry, and superseded planning copies. Final implementation remains at remote `d920ff0`. |
| `/workspace/megaplan-native-parity-corrective/Arnold/.megaplan/runtime/editable-engine` | Old mirror `ab7fff1`: 35/49 dirty source blobs exactly duplicated; 14 unmatched versions were intermediate implementations coherently finalized by `d920ff0` and WBC. | Superseded intermediate source versions and generated files; final implementation remains remote. |

Artifact-only, non-Git directories `/workspace/agent-ui-lifecycle-*`, `/workspace/native-composition-followup`, `/workspace/native-python-parent`, and `/workspace/sequential-model-fallbacks` had no live owning process. Their remaining contents are `.megaplan` telemetry/cache/control artifacts; once any nested Git mirrors listed above are separately handled, these directories are READY-DELETE. What would be lost is old run telemetry/cache, not unique source.

## Stashes

| Owner | Stash contents and evidence | Classification / loss |
|---|---|---|
| `/workspace/megaplan-native-parity-corrective/Arnold` | Seven stashes named `megaplan-chain retry-preserve`, corresponding to failed/intermediate m1–m7 attempts before the completed remote m7/final `d920ff0`. | **READY-DELETE**. Loss is failed retry state only; final coherent implementation is remote. |
| `/workspace/canonical-run-state-control-plane/arnold` | `stash@{0}: pre-rebase-canonical-ledger-state`, four generated ledger files, `+759/-62`; marker is complete. | **READY-DELETE**. Loss is historical generated ledger state only. |
| `/workspace/extension-reality-chain-restart-continuation/arnold` and linked worktree | Shared `stash@{0}: preserve failed repair attempt`, 12 files, `+3750/-1370`; the cloud branch is remote-contained and the marker is archived/cancelled. | **READY-DELETE**. Loss is the failed repair attempt only. |
| `/workspace/reigh-extension-composition-spine-epic-12d49a3e/reigh-app` | One 25-file Reigh stash, `+2323/-90`, alongside unpushed `6e2b328`. | **KEEP — land first** in Reigh. Deleting now loses useful cross-repository work. |

## Codespaces

Codespaces could not be inventoried with the current GitHub token. `gh codespace list --json name,repository,gitStatus,lastUsedAt` returned HTTP 403 with `Must have admin rights`; the direct repository REST attempt returned 404 and identified missing `codespace` scope. This is the sole unavoidable unknown in the cloud estate and must not be interpreted as “no Codespaces.”

Exact resolution step: after explicit authorization to expand GitHub credentials, run `gh auth refresh -h github.com -s codespace`, then rerun `gh codespace list --json name,repository,gitStatus,lastUsedAt` and classify every returned Codespace. No auth mutation was attempted during this survey.

## Deletion-safety conclusion

This report stages recommendations only. Nothing was deleted, pruned, reset, force-pushed, killed, restarted, or discarded. KEEP-land-first entries must remain until the consolidation owner records positive landing/supersession proof. READY-DELETE entries are suitable for the user's per-item approval because their source payload is remote-contained, exactly duplicated, superseded by named final work, or consists solely of generated telemetry/cache.
