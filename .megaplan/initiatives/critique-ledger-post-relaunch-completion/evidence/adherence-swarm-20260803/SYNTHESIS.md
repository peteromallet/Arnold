# Megaplan adherence swarm synthesis

## Scope and result

On 2026-08-03, 25 independent GPT-5.6 Luna high-reasoning audits inspected a
detached snapshot of the integration branch. The bounded matrix covered every
pipeline surface for authority ownership and identity/version/provenance, plus
the five retry/effect surfaces with the highest risk of duplicate mutation or
user-visible effects. All 25 reports completed; none failed to launch.

The raw reports are evidence inputs under `raw/`. Parent adjudication is the
authority: accepted, merged, rejected, and deferred findings are recorded as
MP-001 onward in `../../REMEDIATION_LEDGER.md`.

## Root finding

The incident was not one bad model and not one missing retry. Megaplan had good
canonical primitives, but several production callers treated projections,
local process observations, conventional filenames, or compatibility wrappers
as equivalent authority. Identity and budgets were scoped to a process or
layer rather than the semantic occurrence. That allowed stale evidence to be
adopted, a foreign PID to be called dead, retries to replenish after restart,
and notification or repair effects to bypass their durable boundary.

The generalized correction is:

1. One canonical owner for each mutation.
2. Run, revision, attempt, incarnation, version, and provenance bound at every
   decision/effect boundary.
3. Projections and local `ps`/tmux/PID evidence remain diagnostic.
4. Mutation uses a lock plus expected-version/hash CAS and an allowlisted field
   scope.
5. Retry and effect budgets are durable and occurrence-wide.
6. Ambiguous provider outcomes are `INDETERMINATE` and never fall through to a
   second direct effect.
7. User notifications are admitted once to one outbox and deduplicated by the
   incident occurrence, not by message text or a polling pass.

## Parent overrides of audit proposals

- Durable artifact validity is bound to run/attempt/version/provider and exact
  hashes, not to the continued liveness of the process that created it.
- PID namespace and process-start identity bind mutation custody, not immutable
  evidence validity.
- Exact runtime/profile binding is mandatory for managed cloud authority, while
  explicit local development remains possible.
- Markerless tmux discovery is diagnostic-only and cannot synthesize a managed
  run identity.
- A second notification identity with no active consumer was P1, not P0.
- The exploration stopped at 25 reports because the highest-risk matrix was
  closed; further agents require a concrete uncovered path.

## Relaunch cut

The clean attempt-9 relaunch waits only for the remaining paths capable of
corrupting or duplicating the live attempt:

- correct UNKNOWN liveness handling in wrappers;
- canonical current-target liveness in cloud status/supervisor decisions (raw
  tmux/`ps` remains diagnostic-only);
- normalized repair occurrence and incarnation-bound leases;
- field-scoped transactional `finalize.json` mutation;
- retirement of notification direct-send fallbacks;
- durable occurrence-wide simple-fixer mutation/effect budget;
- combined regression and installed two-container/provider canaries.

Broader Finalize/Execute/launch budget unification, historical wrapper cleanup,
review/epic acceptance consolidation, projection migration, and seven-day
durability remain explicit follow-up work. Deferral does not erase them and
does not count them as fixed.

## Required operational proof

The work is not complete when tests pass locally. Completion requires deploying
one exact integration commit to the cloud candidate, explicitly aborting paused
attempt 8, creating immutable attempt 9, and observing:

- GPT-5.6 Sol high Finalize adopts or recreates the validated candidate through
  the authorized receipt path;
- Finalize advances once, without a third model call or stale rewrite;
- GLM 5.2 Execute starts under the intended profile;
- `/whats-cooking` reports one current r5 run from canonical liveness;
- old v2/r2/r3/r4 attempts remain immutable history, not current work;
- repeated unchanged watchdog polls emit no duplicate Discord notification.
