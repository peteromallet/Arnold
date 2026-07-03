# Loose Work Consolidation Plan

Date: 2026-07-03

## Rationale

This cleanup is not a branch-pruning job. The highest-risk work is spread across
the live local checkout, a remote Hetzner worker volume, non-standard refs, and
cloud workspaces whose state is not visible from `git branch`.

The target end-state is:

1. Every useful Arnold change is recoverable on GitHub, ideally on `main` via
   reviewed PRs.
2. The Hetzner `megaplan-cloud-agent` volume has no cloud-only Arnold source
   changes.
3. Old local worktrees and redundant local branches are removed only after their
   contents are either landed or proven redundant.
4. Non-Arnold cloud work is listed but not merged into Arnold.
5. The cleanup is not complete until the consolidated repair/watchdog code is
   pushed back to Hetzner, `/workspace/arnold` is on `editible-install`, and the
   worker's editable install is refreshed from that branch.

No destructive action is authorized merely by being listed in this plan. The
plan should, however, make explicit delete recommendations at the end: high- and
mid-confidence redundant items can be cleaned after preservation gates pass,
while low-confidence items stay open for human review. Deleting branches,
removing worktrees, deleting refs, pruning cloud workspaces, or dropping cloud
state still requires explicit per-item approval.

## Landscape

### Local Checkout: Item Zero

Current checkout: `/Users/peteromalley/Documents/Arnold`, branch `main`.

State:

- `main` is behind `origin/main` by 3 commits.
- The checkout is dirty with source, docs, tests, and one untracked systemd
  helper.
- The dirty file set changed during survey, so treat the live checkout as active
  work and checkpoint before any integration attempt.

Current local dirty work includes:

- `arnold_pipelines/megaplan/_core/user_config.py`
- `arnold_pipelines/megaplan/chain/__init__.py`
- `arnold_pipelines/megaplan/chain/spec.py`
- `arnold_pipelines/megaplan/cloud/cli.py`
- cloud wrappers: `arnold-progress-auditor`, `arnold-repair-loop`,
  `arnold-repair-trigger`, `arnold-watchdog`
- cloud/epic/prep skill docs and operator docs
- chain/cloud watchdog tests
- `arnold_pipelines/megaplan/prompts/tiebreaker_orchestrator.py`
- untracked `arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog`

Verdict: preserve first, then reconcile. This is not junk. It overlaps with
`origin/editible-install` and with cloud-only `/workspace/arnold` work, but it is
not identical.

### Landed Watchdog Chain

The five-milestone watchdog/repair chain is
`.megaplan/initiatives/tiered-repair-hardening/chain.yaml`.

| Milestone | Branch | PR | State |
| --- | --- | --- | --- |
| M1 cloud-safe substrate | `tiered-repair-m1-substrate` | #129 | merged |
| M2 repair correctness | `tiered-repair-m2-correctness` | #130 | merged |
| M3 triggered repair | `tiered-repair-m3-trigger` | #131 | merged |
| M4 human workflow cloud hardening | `tiered-repair-m4-human-cloud` | #132 | merged |
| M5 meta-audit intelligence | `tiered-repair-m5-meta-audit` | #133 | merged |

Verdict: the chain itself landed on `main`. Keep its initiative metadata and
logs as provenance. The remaining repair/watchdog work is post-chain tail work,
not the M1-M5 branches themselves.

### Local Branches And Worktrees

| Item | State | Verdict |
| --- | --- | --- |
| `editible-install` | local branch, clean worktree at `/private/tmp/arnold-repairer-corrected`; fully contained in `origin/editible-install` | remove worktree, then delete local branch after approval |
| `repairer-meta-retry` | local branch, clean worktree at `/private/tmp/arnold-repairer-meta`; fully contained in `origin/editible-install` | remove worktree, then delete local branch after approval |
| `/private/tmp/arnold-watchdog-ensure-fix` | clean detached worktree; commit is ancestor of `origin/editible-install` | remove after approval |

These local worktrees do not contain unique dirty work.

### Remote Branches

| Branch | State | Verdict |
| --- | --- | --- |
| `origin/editible-install` | 36 ahead / 3 behind `origin/main`, `cherry +33`, merge conflicts; recent repair/watchdog commits | PR-then-merge or consolidate into repair follow-up branch |
| `origin/megaplan/m0-composition-contract-and-20260702-1541` | 1 ahead / 5 behind `origin/main`, clean merge-tree; native composition docs/tests | PR-then-merge, likely as composition follow-up |

### Non-Standard Local Refs

| Ref | State | Verdict |
| --- | --- | --- |
| `refs/temporary/engine-watchdog-runner` | one patch-unique commit for model seam/key-pool Fireworks/DeepSeek routing | cherry-pick or rewrite into follow-up, then delete ref |
| `refs/temporary/live-watchdog-supervisor` | large watchdog/live-supervisor prototype, 59 files | inspect and either PR/archive valuable parts or explicitly drop |
| `refs/snapshots/arnold-m1-m6-wip` | safety snapshot with plan/runtime artifacts and a small number of patch-unique commits | archive or extract useful source/docs before deletion |
| `refs/snapshots/arnold-m7-m8-wip` | larger migration snapshot with source/docs/artifacts | archive or extract useful source/docs before deletion |

Do not delete these refs as "garbage" until the useful payload decision is made.

### Hetzner Cloud Machine

Host: `159.69.51.216`, container `megaplan-cloud-agent`, workspace volume
mounted as `/workspace`.

Active tmux sessions observed:

- `heartbeat`
- `watchdog`
- `megaplan-chain-chain-5a27096e`
- `megaplan-chain-reigh-extension-composition-spine-epic-12d49a3e`
- `preview-picker`

Arnold cloud workspaces:

| Workspace | Repo state | Verdict |
| --- | --- | --- |
| `/workspace/tiered-repair-hardening/Arnold` | clean `main` at `origin/main`; watchdog says chain complete | no source cleanup; keep/archive logs |
| `/workspace/arnold` | `editible-install` at `origin/editible-install`; dirty `arnold_pipelines/megaplan/chain/__init__.py` | highest priority cloud-only source work; checkpoint/port before any cloud cleanup |
| `/workspace/native-python-pipelines-completion-parent-22937539/arnold` | branch `megaplan/m7-megaplan-relocation-and-20260702-0856`, ahead 1 because of audit-only commit `6bf9330c`; actual M7 payload is already pushed as `3fa94fe3` | preserve `6bf9330c` only for audit/history if desired; evaluate `3fa94fe3` as the useful code/doc/test payload |
| `/workspace/native-composition-followup/Arnold` | branch `megaplan/m0-composition-contract-and-20260702-1541`; dirty source/docs/tests plus untracked docs/tests | checkpoint/port into composition follow-up PR; watchdog says needs human review |

Other cloud repos exist for VibeComfy and Reigh. They have their own dirty state
and active sessions, but they are out of scope for Arnold branch cleanup.

### Cloud In-Progress Gate

The cloud machine has active tmux sessions for `watchdog`, `heartbeat`,
`megaplan-chain-chain-5a27096e`, `megaplan-chain-reigh-extension-composition-spine-epic-12d49a3e`,
and `preview-picker`. Of the Arnold workspaces considered by this plan:

| Workspace / session | Cloud status | Merge implication |
| --- | --- | --- |
| `tiered-repair-hardening` | watchdog report says `complete`; no active tmux session for this chain | safe to treat as landed provenance, not in-progress code |
| `/workspace/arnold` / `editable-install` | watchdog actively syncs this editable install; no chain tmux, but it is live infrastructure source | checkpoint before touching; do not assume the dirty file is stable until a fresh diff hash is recorded |
| `megaplan-chain-native-python-pipelines-completion-child` | watchdog says `complete` | child chain is complete |
| `megaplan-chain-native-python-pipelines-completion-parent-22937539` | watchdog says `needs_human`; reason says child survived and re-driving parent would duplicate coordinator work | preserve audit state if desired, but do not treat parent coordination state as completed cleanup until the human decision is recorded |
| `native-composition-followup` | watchdog says `needs_human`; blocked on prerequisite/waiver evidence | in progress/blocked. Checkpoint its dirty code, but do not merge it as finished product work until the blocker is resolved or explicitly waived |

Completion rule: no cloud payload may be called "landed" just because it was
copied locally. The relevant cloud session must be `complete`, or the plan must
record an explicit human decision to preserve a blocked/in-progress checkpoint
without treating it as finished.

## Everything Valuable Lands Here

| Work | Current holder | Lands as |
| --- | --- | --- |
| Repair/watchdog tail work after M1-M5 | `origin/editible-install`, local dirty checkout, `/workspace/arnold` dirty diff | one Arnold repair follow-up consolidation branch/PR |
| Local preflight/prerequisite recovery changes | current dirty `main` | same repair follow-up branch, after non-destructive checkpoint |
| Cloud-only prerequisite/completion authority changes | `/workspace/arnold` dirty `chain/__init__.py` | same repair follow-up branch, reconciled against local dirty `chain/__init__.py` |
| M7 native-python relocation payload | pushed branch commit `3fa94fe3` on `origin/megaplan/m7-megaplan-relocation-and-20260702-0856` | evaluate as real code/doc/test work; PR/merge or deliberately supersede after conflict review |
| M7 audit-only tail commit | `/workspace/native-python-pipelines-completion-parent-22937539/arnold` unpushed commit `6bf9330c` | preserve only if exact cloud audit history is needed; do not merge as useful code |
| Native composition follow-up | `origin/megaplan/m0-composition-contract-and-20260702-1541` and `/workspace/native-composition-followup/Arnold` dirty payload | composition follow-up PR after checkpointing cloud dirty files |
| `engine-watchdog-runner` ref | `refs/temporary/engine-watchdog-runner` | small cherry-pick into repair follow-up if still relevant |
| `live-watchdog-supervisor` ref | `refs/temporary/live-watchdog-supervisor` | separate prototype/archive decision; do not blend blindly into repair follow-up |
| Snapshot refs | `refs/snapshots/*` | archive/extract useful source/docs; generated plan DB/log artifacts likely excluded |

## Deletion Confidence Tiers

After all useful payloads are preserved on GitHub and the Hetzner deployment gate
is satisfied, make delete calls by confidence tier instead of treating all loose
items alike.

| Confidence | Item | Delete recommendation | Evidence required before deletion |
| --- | --- | --- | --- |
| High | Local `editible-install` branch and `/private/tmp/arnold-repairer-corrected` | delete | fully contained in `origin/editible-install`, worktree clean, repair/watchdog consolidation pushed |
| High | Local `repairer-meta-retry` branch and `/private/tmp/arnold-repairer-meta` | delete | fully contained in `origin/editible-install`, worktree clean, repair/watchdog consolidation pushed |
| High | `/private/tmp/arnold-watchdog-ensure-fix` | delete | detached commit is ancestor of `origin/editible-install`, worktree clean |
| High | M7 audit-only tail commit `6bf9330c` as code payload | do not merge; preserve only if audit history is desired | verified diff remains `.megaplan` log-only and `3fa94fe3` remains pushed |
| Mid | Generated/runtime logs and state under cloud workspaces | clean/archive after checkpoint | source/docs/tests have been checkpointed or proven generated-only; live session is complete or human decision is recorded |
| Mid | `refs/temporary/engine-watchdog-runner` | delete only after extraction | useful patch has been cherry-picked/re-written into repair follow-up or explicitly rejected |
| Low | `refs/temporary/live-watchdog-supervisor` | leave open for review | large prototype requires inspect/archive/drop decision; do not default-delete |
| Low | `refs/snapshots/arnold-m1-m6-wip` | leave open for review | snapshot may contain source/docs/provenance; extract/archive decision required |
| Low | `refs/snapshots/arnold-m7-m8-wip` | leave open for review | larger migration snapshot may contain source/docs/provenance; extract/archive decision required |
| Low | Dirty cloud work in `/workspace/native-composition-followup/Arnold` | leave open for review | blocked `needs_human` state and prerequisite/waiver issue must be resolved before merge/delete |
| Low | Any branch carrying useful M7 payload `3fa94fe3` | leave open until PR/supersession decision | evaluate code/doc/test payload; either PR/merge or document that another landed change supersedes it |

End-state rule: the cleanup pass should delete high-confidence redundant items
and any mid-confidence items whose evidence requirements are satisfied. Low
confidence items should remain as named, documented decisions for the human to
grab, review, archive, or explicitly drop.

## Execution Order

1. Freeze the inventory.
   - Re-run local `git status --short --branch`.
   - Re-run read-only Hetzner survey for `/workspace/arnold`,
     `/workspace/native-python-pipelines-completion-parent-22937539/arnold`,
     `/workspace/native-composition-followup/Arnold`, and
     `/workspace/tiered-repair-hardening/Arnold`.
   - Re-read `/workspace/watchdog-report.json` and tmux sessions. If a target
     workspace is `alive`, `running`, or `needs_human`, classify it before
     merging: complete work can be landed; blocked work can only be checkpointed
     until the human decision is settled.
   - Record diff hashes for the local checkout and the two dirty Arnold cloud
     workspaces.

2. Preserve item zero without disturbing the live checkout.
   - Create a scratch worktree or patch bundle from current local dirty state.
   - Include source/docs/tests and `ensure-megaplan-watchdog`.
   - Exclude generated logs and caches.
   - Verify the live checkout diff hash is unchanged afterward.

3. Preserve cloud-only Arnold source work.
   - From `/workspace/arnold`, capture the dirty `chain/__init__.py` diff and
     either commit it to a temporary cloud checkpoint branch or export a patch.
   - From `/workspace/native-composition-followup/Arnold`, capture dirty
     source/docs/tests and untracked docs/tests separately from logs/state.
   - From `/workspace/native-python-pipelines-completion-parent-22937539/arnold`,
     record that unpushed `6bf9330c` is audit-only log state from
     2026-07-02 10:34:51 UTC, not source payload. Preserve it only if exact
     cloud audit history is wanted before cleaning logs/state.
   - For native-python M7, evaluate already-pushed `3fa94fe3` from
     2026-07-02 10:34:37 UTC as the actual code/doc/test payload.

4. Build `consolidate/repair-watchdog-tail-20260703`.
   - Base it on fresh `origin/main`.
   - Merge or cherry-pick `origin/editible-install` first, resolving conflicts.
   - Layer the `/workspace/arnold` cloud-only diff next.
   - Layer the local item-zero repair/preflight/prerequisite changes next.
   - Consider `refs/temporary/engine-watchdog-runner` as a small candidate
     cherry-pick.
   - For every conflict, understand the semantic difference before resolving:
     identify what each side was trying to fix, whether either side is stale,
     and whether the combined behavior changes watchdog, repair, chain
     authority, or editable-install semantics. Make judgment calls explicitly in
     the PR notes instead of defaulting to either side.
   - For difficult judgment calls, ask an independent Codex reviewer using GPT
     5.5 extra-high reasoning, with the conflicting hunks, surrounding code, and
     intended runtime behavior as context. Record the recommendation and the
     final human/agent decision in the consolidation notes.
   - Run focused tests after each layer:
     - `tests/cloud/test_watchdog_wrappers.py`
     - `tests/cloud/test_cloud_chain_command.py`
     - `tests/cloud/test_repair_trigger_wrapper.py`
     - `tests/arnold_pipelines/megaplan/test_chain_awaiting_human_retry.py`
     - `tests/arnold_pipelines/megaplan/test_chain_milestone_validation.py`

5. Build or update the composition follow-up PR.
   - Start from `origin/megaplan/m0-composition-contract-and-20260702-1541`.
   - Add useful source/docs/tests from
     `/workspace/native-composition-followup/Arnold`.
   - Keep generated cloud logs/state out unless intentionally archived.
   - Resolve the watchdog-reported prerequisite/manual-review issue explicitly.

6. Decide the prototype/snapshot refs.
   - Inspect `refs/temporary/live-watchdog-supervisor` as its own prototype.
   - Extract only durable source/docs/tests or archive the whole ref.
   - Inspect `refs/snapshots/arnold-m1-m6-wip` and
     `refs/snapshots/arnold-m7-m8-wip` for useful source/docs before deleting.

7. Push preservation branches and open draft PRs.
   - One repair/watchdog tail PR.
   - One composition follow-up PR if still needed.
   - One archive branch only if the snapshot/prototype material should be kept
     outside `main`.

8. Only after preservation is pushed, clean redundant local/cloud state.
   - Apply the Deletion Confidence Tiers table.
   - Remove high-confidence clean `/private/tmp/arnold-*` worktrees.
   - Delete high-confidence local contained branches.
   - Update `/workspace/arnold` to `editible-install`, fast-forward it to the
     pushed repair/watchdog follow-up code, and refresh the worker editable
     install from that branch.
   - Clean mid-confidence cloud logs/state only when the evidence requirements
     are met and approval is explicit.
   - Leave low-confidence refs/workspaces as documented open decisions unless a
     human explicitly approves archive/drop handling.

9. Prove the final state.
   - Local: `git status --short --branch`, `git branch`, `git branch -r`,
     `git worktree list --porcelain`.
   - Cloud: per-workspace `git status --short --branch`, untracked file list,
     unpushed commit list, and tmux session list.
   - Hetzner deployment gate: `/workspace/arnold` reports
     `## editible-install...origin/editible-install`, has no uncommitted source
     changes, contains the consolidated repair/watchdog commits, and the
     installed worker code is refreshed from that checkout.

## Corrections From Investigation

- The five-milestone tiered repair/watchdog chain was initially missed because
  branch and PR tables hid the chain identity. The authoritative record is
  `.megaplan/initiatives/tiered-repair-hardening/chain.yaml`, and PRs #129-#133
  confirm it landed.
- The cloud machine was initially under-surveyed because the relevant configs are
  `cloud.tiered-repair-hardening.yaml` and
  `cloud.native-representation-epic-chain.yaml`, not `cloud.yaml`.
- `origin/editible-install` is not a stale branch. It is recent repair/watchdog
  tail work with many patch-unique commits.
- The `/workspace/arnold` dirty file is cloud-only loose source work and must be
  reconciled with both `origin/editible-install` and local dirty `main`.
- The non-standard refs are not safe default deletes; several contain
  patch-unique source/docs/prototype work.

## Open Questions

- Whether the local dirty checkout is active human work. Treat it as active until
  checkpointed without disturbing the live diff.
- Whether `live-watchdog-supervisor` should be revived as product code, archived,
  or dropped.
- Whether the native-composition follow-up should wait for the native-python
  completion dependency or land independently with an explicit waiver.
- Codespaces still cannot be surveyed because the active `gh` token lacks the
  `codespace` scope.

## Provenance

Local DeepSeek fan-out:

- `/tmp/arnold-loose-branches-20260703-012000/results/01-current-dirty-vs-editible.txt`
- `/tmp/arnold-loose-branches-20260703-012000/results/02-editible-install-family.txt`
- `/tmp/arnold-loose-branches-20260703-012000/results/03-nonbranch-cloud-clones.txt`

Direct cloud survey:

- Host: `159.69.51.216`
- Container: `megaplan-cloud-agent`
- Configs:
  - `cloud.tiered-repair-hardening.yaml`
  - `cloud.native-representation-epic-chain.yaml`
