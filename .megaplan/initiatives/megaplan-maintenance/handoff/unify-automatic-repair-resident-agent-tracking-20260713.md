# Task: unify automatic repair with resident-managed agent tracking

Implement the structural change requested by the VP: every automatic Megaplan repair worker (including watchdog-dispatched L1 repair, meta-repair/L2, and bounded recovery retries) must be durably tracked through the same managed-agent lifecycle and surfaced with the same operational quality as resident-launched subagents.

## Context

The live Workflow Boundary Contracts corrective chain exposed a custody contradiction. Repair request `7473fa42...` was accepted but projected zero formal claims and attempts while an internal review retry was running. Today automatic repair is primarily tracked through Megaplan repair request/custody records and chain-runner artifacts, whereas resident-delegated Codex work has a durable run ID, manifest, full log, result, model route, lifecycle status, and delivery state. The user wants automatic repair work properly tracked as resident-style subagents too.

This is a cross-cutting control-plane implementation, not a cosmetic projection patch.

## Required outcome

1. Find the actual dispatch and custody seams for watchdog repair-loop, meta-repair, bounded retries, and resident-managed subagents.
2. Establish one shared managed-agent execution/tracking contract. Automatic repair executions must receive truthful durable identities and records equivalent to resident-managed agents: run ID, manifest, log, result, status/history, PID/liveness where applicable, task kind, D1-D10 difficulty, chosen model/reasoning route, timestamps, retry lineage, and terminal outcome.
3. Link each repair run explicitly to its repair request, claim/lease/fence, blocker or incident identity, cloud session, chain, plan, phase/attempt, and parent repair run where applicable.
4. Prefer routing actual repair worker launches through the existing resident-managed lifecycle or a factored neutral managed-agent substrate shared by both paths. Do not manufacture resident records for processes that bypass lifecycle guarantees.
5. Surface automatic repair runs in `resident_agents` or a clearly compatible unified managed-agent view. They must be distinguishable with a truthful `run_kind` such as automatic repair/meta-repair; do not mislabel Discord provenance or ordinary user delegation.
6. Automatic internal repairs normally have no user-facing terminal delivery obligation. Represent delivery as not applicable unless an explicit inbound-message reply contract exists. Never create duplicate Discord replies.
7. Preserve Megaplan repair authority, fencing, retry budgets, idempotency, and chain-runner semantics. One accepted repair must not launch twice because two projections observe it. Crash/restart recovery must adopt or reconcile the same durable run rather than create an anonymous replacement.
8. Legacy or already-running repairs may be shown through a compatibility projection only if their provenance and uncertainty are explicit. Never retroactively claim they were resident-launched or invent claims/attempts.
9. Resolve the accepted-with-zero-claims/attempts contradiction at the source and ensure custody projections agree with managed-agent execution evidence.
10. Add focused regression coverage for L1 dispatch, meta-repair, retries, duplicate dispatch races, restart/adoption, terminal failure, cancellation/supersession, delivery-not-applicable behavior, model routing, and status aggregation.

## Live-chain safety

- Do not restart, cancel, hand-advance, or otherwise disrupt the live Workflow Boundary Contracts chain or its current reviewer.
- Inspect request `7473fa42...` and the current C1 chronology as a concrete validation case, but do not falsify/backfill ownership.
- If safe, prove the next real or fixture repair launch is fully tracked end to end. Do not trigger a destructive live repair merely to obtain proof.
- Preserve unrelated dirty-worktree changes and coordinate with concurrent edits rather than overwriting them.

## Durable documentation

Keep any planning or handoff material under the canonical initiative layout, preferably `megaplan-maintenance/handoff` or `megaplan-maintenance/notes`. Do not create loose `.megaplan/briefs` documents.

## Verification and handoff

Run proportionate focused tests and relevant broader tests. Report:

- the exact shared lifecycle/dispatch design implemented;
- how automatic repair runs now appear operationally;
- evidence against duplicate execution and invented custody;
- what happened with the `7473fa42...` compatibility case;
- test results and any unrelated failures;
- whether a migration or Discord resident restart is required before the behavior is live;
- any remaining safety limitation or human decision.

Do not push, open a PR, or restart services unless separately authorized.

## Implementation handoff (2026-07-13)

Implemented a neutral `arnold_pipelines.megaplan.managed_agent` v2 lifecycle.
The repair queue/watchdog remains the only launch authority; after it wins the
blocker-scoped claim, the managed supervisor atomically binds the claim to its
deterministic run id and real supervisor PID before starting work.  Each run
owns a manifest, append-only status history, full log, result JSON, PID/start
identity, model/reasoning route, D1-D10 difficulty, task/run kind, timestamps,
lineage, links, and terminal outcome.  A per-run nonblocking execution lock
prevents duplicate observers from executing the same accepted identity.  A
restart adopts a still-live worker or reuses the same run directory/id when the
old supervisor and worker are both gone.

Wired real launch seams:

- watchdog L1 -> `automatic_repair`, with the repair request/blocker claim
  transferred under fence to the managed supervisor and the claim lock, owner
  record, bound run, and owner PID recorded in the manifest;
- L1 Codex/Hermes dev-fix and Kimi recovery turns ->
  `automatic_repair_retry`, linked to iteration/attempt and the parent L1 run;
- watchdog L2 shell -> `automatic_meta_repair`;
- L2 Codex orchestrator -> `automatic_meta_repair_worker`;
- L2 ordinary-repair retrigger -> `automatic_repair_retry` with parent and
  retry lineage.

All automatic manifests declare non-Discord provenance and
`completion_delivery.status=not_applicable`.  The resident hot-context
`resident_agents` scan now accepts the shared v2 contract plus legacy resident
v1 manifests and exposes automatic runs with their truthful run kinds, links,
worker PID, history, lineage, terminal outcome, logs, results, and delivery
state.  The Discord delivery sweep still selects only
`resident_delegated_agent`, so internal repair completion cannot reply.

At managed launch, an incident claim and repair-attempt event are emitted from
the actual execution evidence and linked to the manifest.  Repair-data also
records the top managed run and per-attempt managed ids.  No compatibility
record is created for a process that did not cross this supervisor.
The custody projector now validates those references against the actual v2
manifest and projects its observed lifecycle as `managed_agent_execution`.
A missing, invalid, or mismatched manifest is not promoted into a formal
attempt, eliminating zero-attempt projections without inventing custody.

### Live compatibility observation

Request `7473fa422fea89a936d0be64f25468524f0d7d0e1c8632478f5dcfc6ec37860e`
was accepted at `2026-07-11T21:44:32Z` with an empty typed failure/blocker
signature.  It has no active claim and no managed-agent evidence, so it was not
backfilled.  At `2026-07-13T15:58:26Z` the queue recorded it `stale` because the
chain advanced from C1 (`c1-contract-reality-20260711-1433`, now done) to S2
(`s2-contract-foundation-and-20260713-1544`).  The session repair-data remains
legacy/unlinked (`request_id` and `blocker_id` empty); this uncertainty is
preserved rather than relabelled as resident custody.  No live process was
started, stopped, advanced, cancelled, or restarted during inspection.

### Verification

- `tests/test_managed_agent.py`: 10 passed.  Covers L1-compatible claim/attempt
  evidence, complete/failure outcomes, model route, delivery N/A, retry
  lineage, two-process duplicate dispatch, dead-supervisor restart, live-worker
  adoption, cancellation, supersession, unified aggregation, and structural
  L1/L2/retry seams.
- `tests/test_managed_agent.py`, repair contract/request/meta-repair, and
  resident launch suites: 332 passed (12 warnings from existing chain merge
  policy fixtures).
- Broader wrapper-inclusive run: 554 passed / 26 failed.  The managed-launch
  contract assertions found there were updated and pass in focused reruns;
  four meta-dispatch cases that were contaminated by an earlier leaking
  wrapper fixture also pass when isolated.  The remaining 18 reproduce
  unrelated dirty-tree/baseline issues in watchdog setup-deviation and phase
  health strings, scan-lock fixtures, stale PID/maintenance behavior,
  progress-auditor fixtures, meta marker/default strings, and ambient
  resident-provenance injection.  One actual embedded writer regression found
  by the first broad run (`os` import) was fixed.
- Python compilation, `bash -n` for all three wrappers, and `git diff --check`
  pass.

No database migration is required.  Before production behavior changes, deploy
or install-sync these wrapper/Python files and let the watchdog re-exec (or
restart it in a separately authorized operation).  Restart the Discord resident
to load the unified `resident_agents` reader.  Neither service was restarted
here.  The documented Megaplan launcher could not be used in this checkout:
the module lacks `config`, `.venv` is absent, and `uv` is unavailable.
