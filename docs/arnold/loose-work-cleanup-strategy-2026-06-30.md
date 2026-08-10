# Loose Work Cleanup Strategy - 2026-06-30

Target branch: `editible-install`

This records the consolidation decision for the loose branch cleanup. The cleanup
skill was applied to local dirty state, local branches, worktrees, remotes, and
the Hetzner megaplan-cloud worker (`root@159.69.51.216`, container
`megaplan-cloud-agent`).

## Decisions

| Work | Decision | Evidence |
| --- | --- | --- |
| Dirty live checkout cloud/provider payload | Landed on integration branch | Ported as `cloud: retire railway provider and default to ssh`; cleaned hardcoded Hetzner IP and placeholder provider text; `tests/cloud` and import-surface tests pass. |
| Dirty live checkout `sync-skills.sh` rewrite | Landed with cloud cleanup | Keeps canonical skill source at `arnold_pipelines/megaplan/skills` and removes stale retired-skill symlinks. |
| Dirty live checkout cleanup skill rewrite | Landed | Preserves the stronger cleanup process, including current dirty trees, other clones, cloud workspaces, codespaces, subagents, and staged ready-to-delete behavior. |
| Dirty live checkout native-python planning docs | Landed as docs | Preserves the sense-check and epic plan outputs under `docs/arnold/pipelines/`. |
| Cloud-only `/workspace/arnold` wrapper/test fixes | Already landed earlier | Present in `origin/editible-install` before this cleanup as watchdog wrapper hardening; cloud was reset and tested against that tip before the final branch pass. |
| `workflow-manifest-runtime` north-star path fix | Landed | Ported as `workflow: anchor runtime north star for cloud`. |
| `workflow-manifest-runtime` subagent launcher import fixes | Landed in current shape | Restored the minimal terminal runtime fallback and current editable-layout imports without reintroducing the old vendored agent tree wholesale. |
| `cleanup/fan-import-fix-20260628` behavioral golden push-CI fix | Landed | Ported the stronger GitHub push-event `before` SHA behavior from `7eb3b97d`, superseding the weaker `HEAD^` fallback. |
| `origin/python-shaped-workflow-authoring-*` milestone heads | Delete after final verification | DeepSeek audit found M1, M2, and M8 milestone heads are represented by the merged native integration history; no unique useful branch payload remains. |
| `origin/workflow-manifest-runtime` | Delete after final verification | Useful path and launcher fixes were ported; remaining commits are superseded or dead (`shutil` import). |
| `origin/cleanup/editible-tail-20260628` and `origin/cleanup/merge-loose-20260628` | Delete after final verification | Useful cloud, launcher, and CI-golden pieces were ported; remaining cleanup-era payload is superseded. |
| `origin/checkpoint/local-dirty-20260630-005438` | Keep until live checkout is clean | It is the safety copy for the live dirty checkout. Delete only after the final branch is pushed, cloud is verified, and the live checkout is intentionally reset or reconciled. |
| Scratch files `add.py`, `test_glm.txt`, generated `.megaplan` outputs, sample JSON/log files | Delete/drop | Audits found scratch or generated artifacts, not source deliverables. |

## Merge Order Used

1. Start from `origin/editible-install` in a clean integration worktree.
2. Port cloud-provider and skill-sync cleanup as a coherent commit.
3. Port workflow runtime path and subagent launcher fixes.
4. Port behavioral golden CI base-ref logic.
5. Preserve the cleanup skill rewrite and native-python planning docs.
6. Run focused tests locally, push `integrate/final-cleanup-20260630` to
   `editible-install`, then reset and reinstall the cloud worker from that tip.

## Final Deletion Gate

After the final push and cloud verification, the following refs/worktrees are
ready for cleanup:

- Remote branches: `workflow-manifest-runtime`,
  `python-shaped-workflow-authoring-m1-contract-grammar`,
  `python-shaped-workflow-authoring-m2-compiler-core`,
  `python-shaped-workflow-authoring-m8-generated-conformance`,
  `cleanup/editible-tail-20260628`, `cleanup/merge-loose-20260628`.
- Local branches/worktrees: `workflow-manifest-runtime`,
  `workflow-manifest-runtime-subagent-skill`, `cleanup/editible-tail-20260628`,
  `cleanup/merge-loose-20260628`, `cleanup/fan-import-fix-20260628`,
  stale detached scratch worktrees, and the conflicted temporary
  `arnold-editible-install-push` worktree if it contains no unique payload.

`checkpoint/local-dirty-20260630-005438` is intentionally not in the first delete
batch. It remains the fallback until the live checkout is confirmed clean or the
user explicitly approves dropping that safety ref.
