# Resident runtime consolidation — 2026-07-19

## Rationale

The Discord resident had two authoritative but divergent implementation
lineages. Deploying either lineage alone removed working behavior from the
other. This consolidation keeps both and establishes one immutable deployment
source without deleting resident history or replaying durable turns.

Resident state size is not a capacity incident: the live store is about 354 MB
on a volume with more than 200 GB free. Some queries are slow because they
parse all historical turn JSON. Preserve the raw history indefinitely and fix
that separately with indexes/content-addressed snapshots, not retention.

## Preserved sources

| Source | Preserved as | Valuable behavior |
| --- | --- | --- |
| Cloud-only `b92380231941` | `preserve/resident-b923802-20260719` plus verified cloud bundle | Three Discord application commands, status/context, custody, successor queues, scheduling, timeout/reply hardening |
| Provider/Hermes `907935583c6f` | `fix/resident-hermes-resume-recovery` and provider checkpoint branch | Provider-aware managed agents, managed GLM root turns, stable Hermes resume and exact missing-session recovery |
| Live resident data | `/workspace/resident-preservation/20260719Tresident-consolidation/` | Both resident stores, Hermes continuity, logs, recovery evidence, dirty-worktree layers and runtime refs |

The consolidation branch is `consolidate/resident-runtime-v2-20260719`.

## Required runtime contract

- Discord synchronizes exactly `whats-cooking`, `restart-resident`, and
  `dropped-threads`. `fix-the-fixer` remains a strict text command, not a fourth
  application command.
- `/whats-cooking` defers before status collection and responds within the
  Discord interaction deadline.
- Successor queues retain ordered multi-predecessor fan-in, fail-closed custody,
  exactly-one synthesis/delivery ownership, restart persistence, and bounded
  session-log reads.
- Managed provider routing supports Hermes, Codex, and Claude without weakening
  git/effect custody.
- A successful Hermes resume retains the stable session handle.
- Only the exact pre-model Hermes exit-8 missing-session failure may quarantine
  the stale pointer and retry fresh inside the same invocation. No durable turn
  is replayed.

## Deployment gates

1. Compile and run the resident, agentbox, slash-command, queue, scheduling,
   provider, delivery-status, and Hermes recovery regressions.
2. Push the exact tested commit.
3. Materialize a new immutable runtime directory from that commit.
4. Point the service environment at one canonical runtime assignment.
5. Perform a guarded resident-only restart and prove
   `restart_replayed_turns=0`.
6. Require startup evidence showing
   `commands=whats-cooking,restart-resident,dropped-threads`.
7. Verify `/whats-cooking`, a fresh managed-provider turn, a successful resume
   using the same stable handle, and missing-session recovery.
8. Keep all prior runtime and state archives until a separate, per-item deletion
   approval.

## Cleanup boundaries

Safe non-destructive cleanup includes canonicalizing duplicate environment
assignments, persisting Hermes beneath `/workspace`, pushing preservation refs,
and cancelling a duplicate scheduled job through the lifecycle API while
retaining its record.

Do not integrate the dirty scheduling runtime: it contains a rollback of correct
blocked-status behavior. Do not reset the dirty `/workspace/arnold` or
`/workspace/arnold-consolidation-20260714` checkouts. Their committed, staged,
unstaged, untracked, and ignored layers must remain in verified archives.

No resident store, provider state, schedule history, runtime snapshot, branch,
worktree, or archive is physically deleted by this consolidation. Deletion is a
separate Phase 4 action requiring explicit per-item approval.
