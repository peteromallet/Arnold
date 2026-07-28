# Resident and Loose Runtime Consolidation Plan — 2026-07-23

## Purpose

Restore the resident behavior that was omitted when the Custody M9/M10 runtime
line diverged, without changing the immutable F1 runtime of the active M10
chain. Preserve every useful cloud-only or local-only fix, distinguish semantic
ports from superseded commits, and deploy the resident from its own attested
runtime revision.

## Established root cause

The live Discord resident and M10 chain both run the immutable F1 revision
`f1a4b0145bf674a1ac85dd090e7ce7cab51af08a`.

`/whats-cooking` in F1 reads
`/workspace/.megaplan/status/cloud-status.json`. The watchdog rebuilds that
projection hourly, while the resident accepts it as fresh for two hours. The
command therefore showed the 16:20 UTC `initialized` snapshot while the
authoritative journal had advanced through critique, gate, and revise.

A direct foreground projection build on the same F1 runtime took 7.8 seconds
and truthfully reported Custody at 82% overall, `critiqued`, active `revise`,
with a live runner. The projection builder is healthy; invocation-time
collection was lost.

This was branch-lineage omission, not an intentional revert and not a stash
being ignored.

## Immediate resident consolidation

Port these behaviors surgically onto F1, preserving M9 source-cursor,
independent-degradation, unknown-state, and bounded-rendering contracts:

| Order | Source | Behavior | Decision |
|---|---|---|---|
| 1 | `74ff2c138e` | Treat terminal-looking milestone state with a named live successor as running, not a false chain custody mismatch | Port |
| 2 | `eaba46221b` | Group canonically blocked work under attention even if the runner is alive | Port with M9 timestamp/source-cursor safeguards |
| 3 | `613703ddfd` + `7a5f9d39c5` | Build a fresh bounded status root for every command and render the requesting user's timezone | Port together |
| 4 | `1f0b143d8e` | Exclude `megaplan-resident-discord` infrastructure from epic/chain rows | Port |
| 5 | `b8f292e4cd` | Add the live-only, custody-bound `/follow-up` command | Port with bounded live-row resolution |

The older combined freshness commit `303500746c` and cloud-only
`1ffedcadbf` are design evidence, not additional changes; the split
`613703ddfd` + `7a5f9d39c5` behavior is the cleaner source.

### Immediate verification

Run:

- `tests/resident/test_currently_running_command.py`
- `tests/cloud/test_status_snapshot.py`
- `tests/resident/test_discord_follow_up_command.py`
- `tests/resident/test_subagent_followup.py`
- `tests/resident/test_dropped_threads_command.py`
- relevant provenance tests

Then build an immutable resident runtime from the consolidated revision, bind
only the resident marker/service to it, and leave M10's F1 chain runner intact.
Restart through the guarded resident lifecycle. Prove:

1. the resident `/proc` executable and imported source resolve to the new
   attested revision;
2. M10 still resolves to exact F1;
3. `/whats-cooking` generates a current timestamp and current phase on every
   invocation;
4. the timestamp uses the requesting user's `Europe/Berlin` preference;
5. the Discord service marker is absent from active epics;
6. blocked-live work appears under attention;
7. `/follow-up` is registered and returns a durable acceptance receipt without
   claiming task completion.

The resident self-healer must load
`/workspace/.megaplan/resident-runtime.env` after the global cloud hot-env and
must compare the live pane's executable and runtime selector environment to
that resident-specific selection. Without both checks, an ordinary
crash/container restart can silently return the resident to the global F1
runtime while still passing a health command launched from the newer source.

## Other real code absent from F1

These are not part of the emergency resident deployment. Land them on a
successor consolidation branch in dependency order, with focused tests after
each unit:

| Source | Missing behavior | Decision |
|---|---|---|
| `229da73036` | Recover parallel critique from canonical per-check artifacts; represent seeded-empty checks as `unverifiable` | Port |
| `e6967340d5` | Validate every critique plan-version filename/order/hash and bind resolutions to the actual `addressed_in` artifact | Partial semantic port |
| `8389ca09a8` | Preserve tier-selected reasoning effort through execute and adaptive critique routing | Partial semantic port |
| `304c444767` | Version 1–10 complexity routing and correctly map it onto legacy 1–5 profiles | Partial semantic port after reasoning-effort propagation |
| `5e24624711` | Preserve authoritative `awaiting_pr_merge` custody instead of letting terminal plan evidence supersede it | Port |
| `83128c52c1` → `342f044f2f` → `81f48f4cc4` → `a371530b07` → `56bde915bc` → `957caff290` → `19146dfeb5` → `6df848285a` | Validate bounded mutation scopes and bind Superfixer dispatch/import/wrapper selection to exact repaired source | Port as one coherent stack onto the current supervisor runtime library |

The Superfixer stack must be redesigned against F1's
`arnold-supervisor-runtime-lib`; do not restore the older ad-hoc wrappers.

## Proven superseded or already present

Do not port:

- `3978c099ef`: exact patch-equivalent `6633d792c5` is in F1.
- `46b2d718ad`: F1 already preserves a non-empty evaluator payload through
  `76c31645d1`.
- `adcf1a6762`: F1's evaluator prompt/schema already use complexity 1–10.
- Overnight repair fixes `88327293`, `86f7c67c`, `8a3d820b`, and `8ec28d68`:
  their semantics are present in F1 under the consolidated SHAs recorded in
  the Custody port ledger.
- `7b3375bd`: stale phase-cursor rejection is already present in F1's workflow
  projection.
- Older source-hint/raw-verdict Superfixer commits: superseded by the typed
  trigger, circuit-breaker, managed-agent, and commit-custody architecture.

## Stash and dirty-work findings

- The shared local Arnold repository has no stashes and no interrupted Git
  operation.
- The local `main` checkout has extensive unrelated dirty work and is protected;
  no consolidation action may switch, reset, stash, or clean it.
- Custody cloud stash `stash@{0}` is old M8 circuit/recovery work whose
  generalized behavior is already in F1. Custody `stash@{1}` and `stash@{2}`
  contain generated ledgers only.
- All seven native-parity cloud stashes are automatic retry-preserve artifacts
  followed by successful retries in the completed 7/7 epic. None contains the
  resident freshness fix.
- The cloud dirty checkout
  `/workspace/arnold-critique-ledger-runtime-recovery-20260717` contains an
  earlier duplicate freshness design; preserve it until the resident port is
  deployed, then classify it as superseded.
- No stash contains `/follow-up`.

No branch, stash, worktree, or cloud volume is deleted by this plan.

## Execution order

1. Finish and test the resident-only consolidation branch.
2. Commit and push it as the recoverable source of truth.
3. Prepare and attest an immutable resident runtime from that revision.
4. Cut over only the Discord resident; prove M10 remains on F1.
5. Exercise live `/whats-cooking` and `/follow-up`.
6. Continue supervising M10 until the first accepted durable execute batch.
7. After the active M10 code line is stable, create the broader successor
   consolidation branch and land the six non-resident units above in order.
8. Audit the paused critique-ledger epic against the resulting code before
   relaunch; its cumulative cross-round ledger/reconciliation work remains
   incomplete at CL1 (0/5 milestones).
