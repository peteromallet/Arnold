# Local Arnold loose-work inventory

Read-only survey captured 2026-07-14. The comparison anchors are `origin/main`
`7644f55dd9be`, WBC `cbe69337d6f4`, live-checkout checkpoint `8dc3693b7411`,
repair/runtime umbrella `405eb641b0d4`, gate final `790fa2583861`, and
transaction-spine tip `9c3bb63ece9b`. No fetch, checkout, ref update, deletion,
or cleanup was performed by the survey.

Verdicts are final cleanup states:

- **LAND**: include the named payload in this consolidation before deleting its source.
- **KEEP**: exact active/protected reason is stated.
- **READY-DELETE**: positive evidence identifies the successor and what deletion loses.

## Executive inventory

- 36 local branches and 31 `origin/*` branches excluding `origin/HEAD`.
- 32 registered worktrees; 9 were dirty at final enumeration, including this
  authorized consolidation merge.
- 50 standalone Arnold checkout paths across 46 independent common repositories;
  23 dirty and 27 clean at final enumeration.
- 9 stashes in three standalone clones.
- 323 unreachable commits forming 88 unreachable tips.
- No declared submodules. One untracked nested Shannon repository exists.
- No local `refs/pull/*`. Six open GitHub PRs, all drafts.
- One stale `REBASE_HEAD`, but no active rebase directory and a clean worktree.
- 20 patch-file occurrences representing only two unique, tracked patch payloads.

## Item zero: live checkout

`/workspace/arnold` is `main` at `612b139971e1`, 8 behind / 1 ahead of
`origin/main`; its sole local commit is patch-equivalent to `origin/main`.
The working tree contained 78 tracked files (5,260 insertions, 1,672 deletions)
and 155 untracked files. Tracked-diff fingerprint: `bbeee07fabd87ebb947fff05db6349b0fd255111`;
untracked-list fingerprint: `80097ce6f0738292889d7d620507ec69ff868573`.

Safety checkpoint `8dc3693b7411` preserved 212 surveyed file payloads. Eleven
files changed afterward (`layout.py`, `strategy`, and nine skill files), one
deleted path was absent from both states, and nine nested-repository directories
cannot be represented as ordinary blobs.

**Verdict: LAND** the current source/tests/docs through this consolidation.
Treat fan results, `._*`/`.___pycache__`, temporary logs, and replicated scratch
worktrees as **READY-DELETE generated artifacts**. Deleting the live tree before
the consolidation commit would lose the only current versions of the post-checkpoint
files and untracked source/tests.

## Registered worktrees and pinned branches

`b/a` and `cherry+` are relative to `origin/main`.

| Verdict | Branch or detached HEAD | Absolute path | Evidence and loss |
|---|---|---|---|
| **KEEP** | `consolidate/arnold-runtime-activation-20260714` | `/workspace/arnold-consolidation-20260714` | Authorized integration worktree; WBC merge was in progress with conflicts. Keep through commit, tests, and main verification; then ready-delete. |
| **KEEP** | detached WBC `cbe69337d6f4` | `/workspace/arnold-wbc-source-verify` | Authorized clean verification source, b/a 148/5, `cherry +5`. Delete only after verified integration. |
| **LAND** | `main` | `/workspace/arnold` | Live payload described above. |
| **LAND** | `fix/agent-edit-l1-l2-custody-20260714` | `/workspace/arnold/.megaplan/tmp-superfixer-agent-edit/fix-worktree` | Clean umbrella, b/a 5/12, `cherry +11`; lands as `405eb641`. |
| **LAND** | `fix/gate-schema-derived-contract` | `/workspace/arnold-gate-contract-audit` | Clean, b/a 20/2, `cherry +2`; lands as gate final `790fa258`. |
| **LAND** | `fix/transaction-spine-event-projection-20260714` | `/workspace/arnold/.megaplan/tx-spine-systemic-fix` | Clean, b/a 0/4, `cherry +4`; lands as `9c3bb63`. |
| **LAND** | `fix/superfixer-bounded-learning-20260713` payload | `/workspace/arnold/.megaplan/tmp-superfixer-learning` | Branch itself is an ancestor, but two untracked files (`superfixer_episodes.py` and its test) occur in none of main/WBC/checkpoint/umbrella. These two files are genuinely unique. |
| **READY-DELETE after umbrella** | `codex/superfixer-safe-path-20260714` | `/workspace/.codex-worktrees/superfixer-safe-path-20260714` | Clean, b/a 5/9, `cherry +8`; ancestor/subset of `405eb641`. Loss: obsolete stack ref only. |
| **READY-DELETE** | detached `17fb30d3a2a2` | `/workspace/arnold-baseline-check` | Clean ancestor, b/a 5/0, `cherry +0`. |
| **READY-DELETE after successor** | `fix/chain-custody-completion-guards` | `/workspace/arnold-chain-guard-fix` | Branch ancestor; four dirty files are an older 525+/1,113− chain/status implementation superseded by merged PR #191 and later umbrella/WBC contracts. |
| **READY-DELETE** | `fix/chain-custody-guards-min` | `/workspace/arnold-chain-guard-min` | Clean; PR #191 merged into true base `editible-install`. Loss: rewritten-base residue. |
| **READY-DELETE after successor** | `checkpoint/cloud-workspace-arnold-dirty-20260709` | `/workspace/arnold-cloud-dirty-checkpoint-20260709` | Two dirty incident-ledger files are generated ledger churn; old repair intent is covered by current watchdog/repair successors and umbrella. |
| **READY-DELETE after verification** | `checkpoint/cloud-editible-install-dirty-20260713` | `/workspace/arnold-editible-install` | Ancestor branch plus 193-file, 34,375-line deletion snapshot. Current main/WBC/umbrella are the semantic successors; applying it would resurrect obsolete removals. |
| **READY-DELETE** | `checkpoint/cloud-arnold-pre-bf51994fd` | `/workspace/arnold-editible-pre-bf51994fd-checkpoint` | Clean ancestor, b/a 186/0. |
| **READY-DELETE after gate** | `fix/gate-schema-derived-contract-final` | `/workspace/arnold-gate-contract-audit-final` | Clean direct ancestor of `790fa258`. |
| **READY-DELETE** | detached `0f6639785503` | `/workspace/arnold-meta-repair-fallback` | Clean ancestor, b/a 106/0. |
| **READY-DELETE** | `quality-gate-stale-deviations` | `/workspace/arnold-quality-gate` | Clean ancestor, b/a 120/0. |
| **READY-DELETE after umbrella** | `fix/repository-strategy-roadmap-launch-custody` | `/workspace/arnold-roadmap-superfix` | Clean stack subset of `405eb641`. |
| **READY-DELETE** | `terminal-audit-no-model` | `/workspace/arnold-terminal-audit` | Clean ancestor, b/a 117/0. |
| **READY-DELETE** | detached `b401920fd0a4` | `/workspace/arnold/.git/worktrees-tmp/repair-push` | Clean ancestor, b/a 109/0. |
| **READY-DELETE after WBC** | `fix/repair-resume-command-precedence` | `/workspace/arnold/.megaplan/audit-resume-precedence` | Branch `cherry +0`; 7 tracked + 1 untracked pre-WBC authority implementation is superseded by WBC contract reality. |
| **READY-DELETE after umbrella** | `fix/repository-strategy-roadmap-runtime-isolation` | `/workspace/arnold/.megaplan/tmp-roadmap-superfix/fix-worktree` | Clean ancestor/subset of `405eb641`. |
| **READY-DELETE after umbrella** | detached `d63a4de568b5` | `/workspace/arnold/.megaplan/tmp-superfixer-wbc/custody-reconcile` | Seven-commit repair stack is contained semantically by `405eb641` and named successors. |
| **READY-DELETE after umbrella** | local `editible-install` | `/workspace/arnold/.megaplan/tmp-superfixer-wbc/fix-worktree` | Twelve modified generated skill/composed files are obsolete generated output; committed repair intent is in `405eb641`. |
| **READY-DELETE after WBC** | detached `e8143ebccfe7` | `/workspace/context-router-latest-machine-capture` | One old structured-output capture; WBC/gate are the completed successors. |
| **READY-DELETE** | detached `db615eb2ee54` | `/workspace/context-router-machine-capture` | Patch-equivalent to main. |
| **READY-DELETE** | `launch/discord-resident-lifecycle-corrective-20260710` | `/workspace/discord-resident-lifecycle-launch-20260710` | Clean ancestor, b/a 112/0. |
| **READY-DELETE after umbrella** | `checkpoint/cloud-editible-install-durable-20260713` | `/workspace/legacy-editible-durable-reconcile-20260713` | Old durable-runtime checkpoint; repair/runtime intent is in umbrella and named successors. |
| **READY-DELETE** | detached `adcd131052ed` | `/workspace/prompt-fix-final-reconcile` | Patch-equivalent to main. |
| **READY-DELETE** | detached `d4340acdb2d9` | `/workspace/prompt-fix-machine-capture` | Patch-equivalent to main. |
| **READY-DELETE** | `integrate/resonance-full-runtime-20260713` | `/workspace/resonance-full-reconcile-20260713` | Clean ancestor, b/a 60/0. |
| **READY-DELETE after WBC** | detached `826863ceb3d6` | `/workspace/wbc-c1-root-corrective-20260711` | Ten dirty boundary files plus one test are the pre-publish WBC corrective state; WBC `cbe6933` is the semantic successor. |

## Other local branches

Primary **LAND** inputs are only the live checkpoint/current tree, `405eb641`,
`790fa258`, `9c3bb63`, WBC `cbe6933`, and the two unique superfixer episode files.

The following refs are **READY-DELETE after those inputs are verified**:

- Checkpoints: `checkpoint/cloud-arnold-pre-runtime-ref-fix-20260713-2150-runtime-ref-fix`,
  `checkpoint/cloud-audit-pre-runtime-ref-fix-20260713-2150-runtime-ref-fix`,
  `checkpoint/cloud-workspace-arnold-20260709`,
  `checkpoint/cloud-workspace-arnold-dirty-20260709`,
  `checkpoint/cloud-editible-install-durable-20260713`, and
  `checkpoint/local-main-dirty-consolidation-20260714T124424Z`. Their loss is
  historical snapshot state; their intended source changes are represented by
  the primary inputs/successors.
- Patch-equivalent/ancestor refs: `codex/meta-audit-current-target`,
  `codex/meta-audit-publish`, `deploy/discord-resident-20260714`,
  `fix/auditor-github-sync-fanout`, `fix/c1-repair-unavailable-root-corrective`,
  `fix/evidence-accounting`, `fix/meta-recursion-no-relaunch`,
  `integrate/resonance-full-runtime-20260713`,
  `launch/discord-resident-lifecycle-corrective-20260710`,
  `quality-gate-stale-deviations`, `rescue/cloud-runtime-dirty-20260713`, and
  `terminal-audit-no-model`.
- Stack subsets: `codex/superfixer-safe-path-20260714`, `editible-install`,
  `fix/repository-strategy-roadmap-launch-custody`,
  `fix/repository-strategy-roadmap-runtime-isolation`, and
  `fix/wbc-superfixer-recovery-20260713`; successor is `405eb641`.
- `megaplan/progress-auditor-stage-metrics/m1`: PRs #140/#158 merged into
  `editible-install`; both commits are `git cherry -` against current
  `origin/editible-install`.
- `fix/chain-custody-guards-min`: PR #191 merged into its true base.

`main` remains protected.

## Remote refs and pull requests

**KEEP**:

- `origin/main`: protected default.
- Draft PR heads: `origin/megaplan/repository-strategy-roadmap/m4-migration-compatibility`
  (#248), `origin/megaplan/runauthority-epic/m1-foundation` (#213),
  `origin/megaplan/megaplan-maintenance/m2-authority` (#211),
  `origin/epic/extension-reality-m1-trust-model-truth` (#208),
  `origin/cloud/vibecomfy-trust-correctness-2026-07/sprint-1` (#206), and
  `origin/megaplan/runauthority-sprint-1/m1` (#205).
- `origin/local/extension-foundation-completion` and related extension refs are
  protected dependencies of draft PR #208.
- `origin/megaplan/s4-consumption-and-general-20260714-0128` (`cbe6933`) until
  WBC integration is verified.

**LAND**: `origin/editible-install` (`405eb641`, b/a 5/12, `cherry +11`) and WBC.

**READY-DELETE after successors**:

- `origin/fix/repository-strategy-roadmap-launch-custody`,
  `origin/fix/repository-strategy-roadmap-runtime-isolation`, and
  `origin/fix/wbc-superfixer-recovery-20260713` after `405eb641`.
- WBC predecessors `origin/megaplan/c1-contract-reality-20260711-1433`,
  `origin/megaplan/s2-contract-foundation-and-20260713-1544`, and
  `origin/megaplan/s3-megaplan-boundary-coverage-20260713-1934` after WBC.
- `origin/cloud/extension-reality-chain-restart-continuation` and repair-tail
  refs `origin/phase-failure-telemetry`, `origin/repair-live-handoff`,
  `origin/repair-live-handoff-reason`, `origin/repair-pr-evidence`,
  `origin/repair-preserve-target-repo`, `origin/repair-terminality-contract`,
  and `origin/unicode-decode-fix`: semantic successors are the current repair/
  watchdog umbrella plus `e366`, `6089`, `4adb`, `c056`, `45dd`, `d47`, `fdb`.
- Already-main ancestors: `origin/checkpoint/cloud-editible-install-dirty-20260713`,
  `origin/consolidate/native-parity-cloud-20260710`,
  `origin/repair/stale-planned-state-mismatch-20260710`, and
  `origin/rescue/cloud-runtime-dirty-20260713`.
- `origin/megaplan/repository-strategy-roadmap/m2-lifecycle-integration`: PR #237
  merged; remaining ref is init-state residue.

No local `refs/pull/*` and no external open PR heads were present.

## Standalone clones and nested repositories

### Dirty checkouts

**KEEP — active draft PR**:

- `/workspace/extension-reality-convergence-epic/reigh-app` (#208)
- `/workspace/megaplan-maintenance/Arnold` (#211)
- `/workspace/runauthority-epic-all-codex/Arnold`,
  `/workspace/runauthority-epic-d58c26ea/arnold`, and
  `/workspace/runauthority-epic/Arnold` (#213 family)
- `/workspace/runauthority-sprint-1/Arnold` (#205)

`/workspace/repository-strategy-roadmap/Arnold` became clean during the survey;
keep it only while draft PR #248 remains active.

**READY-DELETE after semantic successor/PR verification**:

- `/workspace/.megaplan/repository-strategy-roadmap-supervisor-source`
- `/workspace/canonical-run-state-control-plane/arnold`
- `/workspace/custody-control-plane-240c2cca/arnold`
- `/workspace/discord-resident-lifecycle-corrective-20260710/Arnold`
- `/workspace/extension-reality-clean-lane-recovery/arnold`
- `/workspace/extension-reality-final-verify`
- `/workspace/megaplan-native-parity-corrective/Arnold`
- `/workspace/megaplan-north-star-sense-checks-revise-design/arnold`
- `/workspace/progress-auditor-stage-metrics/Arnold`
- `/workspace/runauthority-epic-cloud/Arnold`
- `/workspace/superfixer-alive-but-failed-recovery/Arnold`
- Dirty nested mirrors:
  `/workspace/extension-foundation-completion/reigh-app/.megaplan/runtime/editable-engine`,
  `/workspace/megaplan-native-parity-corrective/Arnold/.megaplan/runtime/editable-engine`,
  `/workspace/native-python-pipelines-completion-parent-22937539/arnold/.megaplan/runtime/editable-engine`,
  `/workspace/progress-auditor-stage-metrics/Arnold/.megaplan/runtime/editable-engine`,
  `/workspace/sequential-model-fallbacks/Arnold/.megaplan/runtime/editable-engine`, and
  `/workspace/superfixer-alive-but-failed-recovery/Arnold/.megaplan/runtime/editable-engine`.

Positive evidence: these are old epic/runtime snapshots; their source intent is
covered by merged PRs, WBC, current main, `405eb641`, or the named semantic
successors. Loss is generated ledger/runtime state and obsolete intermediate
implementations, not a remaining product delta.

### Clean checkouts

Keep `/workspace/workflow-boundary-contracts-corrective-20260710/Arnold` and
`/workspace/wbc-editible-ra-integration` only through WBC verification.
`/workspace/runauthority-epic-engine-fix` is ready-delete after umbrella/successor
verification. `/workspace/extension-reality-chain-restart-continuation/arnold`
is clean but owns a stash addressed below.

All other clean standalone/nested runtime mirrors are **READY-DELETE with their
parent clone** after active PR/WBC/umbrella verification:

- `/workspace/agent-edit-canonical-deltas/vibecomfy/.megaplan/runtime/editable-engine`
- `/workspace/agent-edit-verifiable-transaction-spine/vibecomfy/.megaplan/runtime/editable-engine`
- `/workspace/arnold/.megaplan/tmp-push-watchdog-fix`
- `/workspace/canonical-run-state-control-plane/arnold/.megaplan/runtime/editable-engine`
- `/workspace/custody-control-plane-240c2cca/arnold/.megaplan/runtime/editable-engine`
- `/workspace/discord-resident-lifecycle-corrective-20260710/Arnold/.megaplan/runtime/editable-engine`
- `/workspace/extension-reality-chain-restart-continuation/arnold/.megaplan/runtime/editable-engine`
- `/workspace/extension-reality-chain-restart-continuation/arnold/.worktrees/fix-chain-custody-guards-min`
- `/workspace/extension-reality-clean-lane-recovery/arnold/.megaplan/runtime/editable-engine`
- `/workspace/extension-reality-convergence-epic/reigh-app/.megaplan/runtime/editable-engine`
- `/workspace/extension-reality-m3-m4-recovery`
- `/workspace/megaplan-maintenance/Arnold/.megaplan/runtime/editable-engine`
- `/workspace/megaplan-north-star-sense-checks-revise-design/arnold/.megaplan/runtime/editable-engine`
- `/workspace/reigh-extension-composition-spine-epic-12d49a3e/reigh-app/.megaplan/runtime/editable-engine`
- `/workspace/repository-strategy-roadmap/Arnold/.megaplan/runtime/editable-engine`
- `/workspace/runauthority-epic-cloud/Arnold/.megaplan/runtime/editable-engine`
- `/workspace/runauthority-epic-d58c26ea/arnold/.megaplan/runtime/editable-engine`
- `/workspace/runauthority-epic/Arnold/.megaplan/runtime/editable-engine`
- `/workspace/runauthority-sprint-1/Arnold/.megaplan/runtime/editable-engine`
- `/workspace/vibecomfy-trust-corrective-2026-07/vibecomfy/.megaplan/runtime/editable-engine`
- `/workspace/vibecomfy-trust-correctness-2026-07/vibecomfy/.megaplan/runtime/editable-engine`
- `/workspace/workflow-boundary-contracts-corrective-20260710/Arnold/.megaplan/runtime/editable-engine`

Deleting these loses only clean detached runtime snapshots already represented by
their parent effort or successor.

Nested non-Arnold repo `/workspace/arnold/megaplan/vendor/shannon` is clean at
`c38691f`, exactly tracking its own `origin/main`, but untracked by Arnold.
**LAND** it only through an explicit vendor/submodule decision; otherwise deletion
would lose the intended Arnold-to-Shannon linkage.

Several old clones contain credential-bearing remote URLs. Values are intentionally
omitted; sanitize the remotes and rotate the credential.

## Stashes

All nine are **READY-DELETE after successor verification**, not LAND:

- `/workspace/canonical-run-state-control-plane/arnold` `stash@{0}`: four
  incident-ledger files, 759+/62−; generated pre-rebase ledger state.
- `/workspace/extension-reality-chain-restart-continuation/arnold` `stash@{0}`:
  12 files, 3,750+/1,370−; failed repair attempt superseded by merged extension
  work and current chain/watchdog successors.
- `/workspace/megaplan-native-parity-corrective/Arnold` `stash@{0..6}`: seven
  retry-preserve snapshots (up to 13,338 additions). Their intended native/
  auditor/watchdog changes exist in current main/WBC and successors `3bf`, `881`,
  `f98`, `d47`, `fdb`, and `5fd`; applying them would restore obsolete intermediate
  contracts and generated ledgers.

Loss is historical retry/ledger state and superseded code variants.

## Unreachable objects

`git fsck --unreachable --no-reflogs` found 323 commits, 88 tips, 1,648 trees,
and 1,550 blobs. Stable-patch/tree comparison against all current refs and the
six anchors produced 23 exact tip matches (11 tree, 12 patch). The remaining 65
were reconciled semantically and against refs in other local clones.

**Final verdict: all 88 unreachable tips are READY-DELETE. No unique orphan tip
remains to land.** The earlier mechanical LAND calls were false positives caused
by rebases/context changes and checkpoint aggregation.

Semantic successor map used for the correction:

- Resident correlation → `c501c6a`
- Runtime isolation → `991756`
- Preserve target repo → `e366`
- Budget requeue → `6089`
- Recurrence → `4adb`
- Needs-human classification → `c056`
- Chain-done classification → `45dd`
- Epic parents → `03a`
- Plan/chain reconciliation → `ae248`
- Model routing → `31c7`
- Auditor variants → `3bf`, `881`, `f98`
- Watchdog variants → `d47`, `fdb`
- Stale dependency manifests → `206`
- Execute policy/observability → `5fd`

The 65 non-exact tips and final evidence are:

- Superseded source variants: `abdf7ec2ad2d` (Discord status/restart),
  `de4080bee37d` and `29516b6dc064` (resident correlation → `c501c6a`),
  `bc90fd0ae4ba` and `6c722ed591bb` (runtime isolation → `991756`),
  `be5a6f48abcb` (target repo → `e366`), `5bf33c1bda4e` (budget → `6089`),
  `ae62f2cc7b4b` (recurrence → `4adb`), `b8cd3b96627f` (needs-human → `c056`),
  `d0505109e80a` (chain done → `45dd`), `906bf632c78d` and `d243132a40ad`
  (epic parents → `03a`), `5784e59165a7` and `acb42b1ab7f5` (reconciliation
  → `ae248`), `69460d06b7f8` (model routing → `31c7`), `f4c597cef225` and
  `4ffc0c9b2c46` (auditor → `3bf`/`881`/`f98`), `3d3ed4276c8b` (watchdog
  → `d47`), `badbbc271f53` (manifests → `206`), `243a2535f7e9` and
  `c297c502e76a` (watchdog → `fdb`), and `2f9ec2f5a0de` (execute policy → `5fd`).
- Gate intermediates superseded by reachable `94abc498`/`790fa258`:
  `6449b831a5d9`, `30165793eb7f`, `35a66d71f12a`, `fcc4bceff358`,
  `9152222586c5`; `645443272c2c` already has exact gate-tree results.
- Checkpoint/stash variants whose intended changes are in the successor map:
  `f569a8095bb0`, `399194cd1f4a`, `5cada1f72b8c`, `851c6c3568ce`,
  `36cbb4a21c10`, `19c9de1dab5d`, `29e93f6ee246`, `fb51e9cfeb68`,
  `d465ebbe0540`, `36830ca6bd73`, `321153b60c74`, `fca0740c39a9`,
  `04c3da1343f2`, `124be1d6ddf1`, and `55b748300510`.
- Protected in other clone refs or merged PR history: `79c738051d3f` (PR #236),
  `51c4a63a4bd0` (PR #204), `80267711688a`, `2907c5ac00d5`,
  `9904efea6367` (PR #191), `d362f9a2aacd` (PR #183), `8b43cba083c4`
  (PR #190), `1ae2757e8bc6`, `aca697fdedfc` (PR #158), and `82fb36dd7767`.
- Semantically present in current main/configuration: `74dd75854df2` (GPT-5.6
  all-codex profile); `f7f0ed49aaf3` has exact file results in every anchor and
  the integration worktree; `42b35f7d5cce` and `1b9d194954ca` are old
  repair/watchdog syncs covered by successors.
- Pure run metadata/generated samples: `3c5be811134a`, `ba415f6f64b9`,
  `98e0285879c7`, `77a0ce8fde8d`, and `5042a9c728a1`.
- Historical safety trees superseded by completed migration/main:
  `5af571620d98` and `f124c62b7aa9`; applying them would restore obsolete
  110-/1,121-file repository states.
- Older already-merged/import variants: `7bf97f442967` (PR #127).

What pruning loses: obsolete commit topology, historical stash/checkpoint trees,
generated run metadata, and superseded implementation variants. It loses no
remaining product payload after the named successors and active consolidation
are verified.

## Other leftovers

- No `.gitmodules`; no declared submodule state.
- `/workspace/arnold-gate-contract-audit` contains stale `REBASE_HEAD`
  `30165793`, but has clean status and no `rebase-apply`/`rebase-merge`; metadata
  is ready-delete with that worktree.
- Two tracked accidental-native-diff patches (254 and 250 lines) appear ten times
  each solely because registered worktrees expose the same tracked files. Duplicate
  copies are ready-delete with their worktrees; canonical tracked copies remain.

## Required ordering

1. Finish and verify this consolidation: live payload, WBC, `405eb641`,
   `790fa258`, `9c3bb63`, and the two unique superfixer episode files.
2. Preserve active draft-PR clones/refs until their PRs resolve.
3. Verify the semantic-successor SHAs above in the final tree.
4. Only then request explicit per-item approval for branch, worktree, stash,
   clone, or unreachable-object deletion.
