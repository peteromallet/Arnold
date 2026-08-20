# Independent Sol-high adjudication — shortest safe Critique Ledger relaunch

You are an independent GPT-5.6 Sol-high reviewer. This is a read-only sequencing
and safety adjudication. Do not modify code, git, checklist, cloud/provider
state, owners, markers, plans, processes, deployments or existing reports. Write
only the result report named below.

## User outcome

Find the **shortest defensible route** to launch a fresh Critique Ledger v3 epic
on cloud and prove one authoritative transition beyond the prior `gated` stall.
Do not require broad platform perfection before that one-transition canary. Do
not waive a reproduced false-success, duplicate-effect, unsafe retry,
notification-amplification, lost-evidence or broken-fence path on the actual
launch route.

Everything that does not block that bounded outcome must be moved into a
follow-up Megaplan epic, preserving the obligation rather than deleting it.

## Human goal and success hierarchy

The user's goal is not merely to make a launch command return successfully.
Reconstruct their intended outcome as follows, in priority order:

1. **Recover the actual Critique Ledger work.** A fresh successor must run on the
   cloud machine, get past the state where v2 stalled, continue through the
   ordinary epic milestones, produce real feature work, and ultimately deploy
   that product. The immediate decision in this review is only how little must
   happen before the first safe v3 transition; the rest must remain scheduled.
2. **Make movement durable.** Process liveness, a marker, a bot message or a
   nominal plan state is not success. Owner records must prove the exact launch,
   transition and resulting authority. Crash, response loss or restart must
   reconcile without a second launch/effect.
3. **Fix what failed at the root.** The system should recognize stalled,
   rejected, unknown and unverifiable outcomes accurately. A failed critic must
   not be projected as clean; recovery delegation must have real provenance; an
   eligible failure should reach one authorized fixer automatically when safe.
4. **Stop notification amplification.** The resident/bot sent the same human-
   review alert repeatedly. One canonical occurrence should yield one initial
   notification and only meaningful state-transition/reminder messages under a
   quiet, durable policy. Repeated observation of unchanged failure must be
   silent.
5. **Keep a definitive ledger.** Operators and automated fixers need one
   trustworthy, queryable account of occurrence, attempts, model/provider raw
   evidence, decisions, claims, effects, reconciliation, repairs and
   notifications. Projections/log prose must not become authority.
6. **Generalize without holding recovery hostage.** Root defects should be fixed
   in reusable platform boundaries that help all pipelines, not patched only for
   Megaplan. But platform-wide adoption, exhaustive cleanup and defense-in-depth
   that the v3 path does not exercise should run in the follow-up epic rather
   than delaying the bounded canary.
7. **Use independent agents as critics, not authorities.** Luna and Sol outputs
   are evidence. Root must exercise judgment, override speculative requirements,
   and require concrete reproduction for new blockers.
8. **Finish the whole obligation in two stages.** Stage A is the shortest safe
   cloud relaunch and independently accepted first transition. Stage B is a
   durable follow-up Megaplan epic containing every deferred hardening item,
   ordinary completion of v3, product deployment, incident institutionalization
   and real 24h/72h/7d observation. No obligation may disappear at the cut.

The user explicitly rejected an outcome where an exhaustive platform rewrite
makes the relaunch appear only 28–40% complete after substantial work. Your
review must therefore expose accidental prerequisite inflation and give the
shortest safe route, while remaining candid if a specific unclosed defect can
still reproduce the original failure or notification loop on the actual route.

## Primary sources to read

1. Full 55-task recovery checklist and incident evidence:
   `/Users/peteromalley/Documents/Arnold/docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`
2. Current durable orchestration state:
   `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/ACTIVE_STATE_20260802_1712.md`
3. Luna's broad task-by-task cut:
   `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/SEQUENCING/relaunch-cutline-luna-audit.md`
4. Draft follow-up epic:
   `/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/critique-ledger-post-relaunch-completion/chain.yaml`
   plus its `NORTHSTAR.md`, `briefs/`, and `proof-map.json`.

Read the relevant candidate/review reports under:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/`.
At minimum inspect the latest reports for T0.0, T1.1, T1.3, T1.5, T1.7,
T1.8, T1.10, T2.2/T2.3/T2.6, T3.1-T3.6 preparation, T4.1-T4.6 preparation,
and T5.1-T5.6 preparation where present.

## Known current facts

- Original v2 did not complete CL2. It stopped at `gated -> finalize ->
  manual_review`; execution never began and no feature PR exists.
- Repeated resident notifications reported the same stalled occurrence and a
  failed diagnostic launch:
  `DelegationProvenanceError: cloud session marker has no resident delegation provenance`.
- The three model tiers were DeepSeek v4 Flash, DeepSeek v4 Pro and GLM 5.2.
  Model failures mattered, but fail-open admission and split recovery/effect
  custody were the decisive system defects.
- Accepted formal evidence currently includes T0.2 preservation and T0.4 target
  inventory. No cloud mutation, v2 fence, v3 launch or product deployment has
  occurred.
- RA-CONTAIN candidate `48e13e1b...` independently passed locally but lacks an
  installed production owner receipt.
- T1.1 raw-evidence admission candidate `3ed353f8...` is under independent
  Sol-high review and has known questions around a non-production backend seam,
  root milestones, revisionless projection and missing production owner lookup.
- T1.3 contract-bundle candidate `40992256...` independently HARD FAILED pass 5
  because public `ProviderTranscript.capture_transport` lets ordinary callers
  choose physical route/session/attempt data and self-set authenticated status.
  This is a real normal-API bypass, not arbitrary `__code__` takeover.
- T1.5 `simple_fixer` prior candidate HARD FAILED on caller-minted authority,
  forged stored-result replay, still-live legacy launch/copy routes,
  caller-mintable fix-the-fixer, provenance-detail amplification and 741 hidden
  assertions. A bounded repair is active.
- T1.8 release-generation candidate `26d24033...` is under independent Sol-high
  review after repairing live generation/manifest recomputation and displaced
  writer lineage across crash/replay.
- T1.10 notification candidate remains HARD FAIL: direct writers, unbound
  runtime, no signed key rotation and incomplete reminder/child-key semantics.
- T1.7 generic transactional owner store is being implemented, but whether
  adopting it everywhere blocks the first v3 transition is disputed.
- Downstream T2/T3/T4/T5 runbooks and gate matrices largely exist as read-only
  preparation; the integrated/deployed candidate and owner decisions do not.
- Common clean integration ancestor is
  `6787d6363e8fc0603092913ae877db14f3b9fff8`; main is dirty/diverged and is not
  an integration target.
- Retired `megaplan-cloud`, raw `cloud chain --fresh`, tmux, marker editing and
  watchdog relaunch are not valid authority paths.

## Competing cuts to adjudicate

### Broad Luna cut

All T0/T1/T2, T3 release receipt, T4.1-T4.5, T5.1-T5.6, T6.1 and T6.2 block the
safe canary. T4.6 and T6.3 onward follow it. This produced a conservative
estimate around 28-40% complete.

### Root's proposed narrow cut

1. Close the ordinary model-attempt self-attestation bypass.
2. Make one failure produce one canonical fixer occurrence and one deduplicated
   notification.
3. Install and attest one exact rollback-capable control-plane generation.
4. Permanently deny every v2 effect and move selection away from it.
5. Create v3 with fresh identities and a one-transition expiring launch envelope.
6. Launch and verify that transition from owner records.

Generic owner-store adoption everywhere, exhaustive legacy retirement, full
cross-pipeline conformance, archival work and long observation windows would be
follow-up unless the actual launch path depends on them.

## Required analysis

1. Trace the exact intended production path from accepted source candidate to
   installed cloud generation, v2 fence, v3 admission, launch, first model
   attempt, first state transition, fixer eligibility and notification.
2. For every original task T0.0-T8.5 classify:
   - `MUST_BEFORE_LAUNCH`
   - `MUST_BEFORE_FIRST_TRANSITION_ACCEPTANCE`
   - `FOLLOW_UP_EPIC`
   - `REDUNDANT_OR_MERGE` (only if its obligation is fully subsumed; name where)
3. A task may block only if you identify its exact actual-route consumer and a
   concrete failure if absent. Distinguish local implementation acceptance,
   integration, installed attestation and production owner receipt rather than
   treating them as one giant task.
4. Identify the smallest coherent integration set: exact candidate commits or
   bounded repairs required, dependency/order, tests, owner decisions and
   deployed receipts.
5. Explicitly decide whether T1.1, T1.2, T1.4, T1.6, T1.7, T1.9 and T2.1-T2.6
   genuinely block the bounded canary, and whether any can be scoped to only the
   exercised route.
6. Explicitly decide how much of T1.5's 741-test retirement and T1.10's full key
   rotation/reminder design blocks the canary versus only the proven live
   bypass/duplicate-message paths.
7. Give a finite stop rule preventing new speculative prerequisites: what exact
   evidence is sufficient to launch, and what classes of reviewer finding may
   still reopen the gate?
8. Recut the follow-up epic into right-sized milestones. Include every deferred
   obligation, platform-wide generalization, product completion/deployment,
   incident closeout and 24h/72h/7d observation. State if the current six
   milestone draft is missing deferred pre-launch hardening.
9. Estimate progress toward (a) issuing the bounded launch and (b) accepting the
   first transition. Use an evidence-weighted range and explain what it does and
   does not mean; do not use equal task counting.

## Judgment constraints

- Resist both extremes: do not rubber-stamp a reckless shortcut, and do not
  turn recovery into a total platform rewrite.
- Do not require mathematical impossibility, arbitrary interpreter takeover
  defenses, speculative refactors, post-launch documentation or observation to
  start one narrowly authorized transition.
- Ordinary public/import/direct-module paths on the deployed generation are in
  scope. Reproduced caller-minted authority, false success, duplicate side
  effect, resend, broken fencing, evidence corruption or unsafe response-loss
  behavior is a blocker.
- Prefer scoping/denylisting an unused route over rebuilding the whole platform
  when that is safe and testable.
- No recommendation may use retired or direct state-mutation paths.

## Output

Write a self-contained report to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/SEQUENCING/shortest-safe-relaunch-sol-high-result.md`

Include:

- executive verdict;
- exact shortest critical path, ordered and parallelized;
- all-task classification table;
- required integration/deployment/owner evidence;
- explicit launch GO/NO-GO predicate;
- follow-up epic milestone map;
- progress range;
- disagreements with Luna and root;
- report SHA-256.

Do not change the current plan or epic; root will apply accepted sequencing after
review.
