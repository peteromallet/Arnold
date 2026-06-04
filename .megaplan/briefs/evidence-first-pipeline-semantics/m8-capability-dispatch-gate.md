# M8: Capability Dispatch Gate

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Make every complexity-routed dispatch (primarily execute) emit CAPABILITY
EVIDENCE: the adjudicated complexity tier, the actual model dispatched, its
capability class, the batch/task evidence it belongs to, the authority-proven
availability basis, and the `routing_resolution_decision` from M7 that produced
the route.

Add a `TransitionPolicy` gate that flags/blocks (or records an explicit scoped
waiver) when the ACTUAL model ran below the ADJUDICATED tier. The gate checks the
adjudicated tier, not the resolved spec, so stale or degraded routing cannot
launder itself into adequacy.

Closes the silent premium->DeepSeek execute degrade: complexity-4/5 tasks ran on
DeepSeek because the profile model-floor decided "no premium available" from an
env-var-only credential check that was blind to CLI-subscription auth, and nothing
verified that the task ran on a model adequate for its complexity. The hardest
tasks routinely landed on an underpowered model and shipped broken/incomplete code.

Relationship to M5: M5 adds *worker capability for EVIDENCE* (can this worker
produce the required objective evidence). M8 is distinct — it gates *execute MODEL
adequacy vs the adjudicated complexity tier*. M8 should reuse M5's transition
policy and waiver model rather than duplicate them.

## Scope

IN:

- A per-dispatch capability `EvidenceRef`: `{task id, adjudicated tier, requested
  model spec, actual model, capability class, availability-resolution basis,
  routing_resolution_decision id}`.
- Resolve model availability against authority-proven dispatch auth (key pool /
  CLI-subscription / agent availability), not env-var presence or binary
  availability proxies; record the basis.
- A capability gate in `TransitionPolicy`: a task whose actual model capability is
  below its adjudicated tier is a policy violation — block under `enforce`, warn
  under `warn`, with an explicit scoped waiver (actor/reason/expiry) when intentional.
- Surface capability degradations in status/chain/cloud summaries (loud), reusing
  the `routing_degradations` signal.
- Cover the finalize-adjudication -> execute-dispatch handoff so the tier the
  adjudicator assigned is the tier the gate checks.
- Emit batch-level task evidence so parallel/batched dispatch cannot hide a sub-tier
  task behind a mixed batch summary.
- Require capability evidence to cite M7's `routing_resolution_decision`.

OUT:

- Do not change complexity ADJUDICATION itself (finalize owns scoring).
- Do not duplicate M5's worker-evidence-capability check; extend/reference it.
- Do not hard-pin a uniform execute model — per-task routing economics stay.
- No new credential system; consume the existing key pool / agent availability.

## Locked Decisions

- The model a task ran on is EVIDENCE, recorded with its availability basis — not a claim.
- "Available" means authority-proven actually-dispatchable (CLI/subscription/key-pool), not env-var presence or binary availability.
- A sub-tier dispatch is a waiver-able policy violation, never a silent degrade.
- The gate compares ACTUAL model capability to ADJUDICATED tier, not to a resolved spec that may already contain the degradation.
- Batch dispatch must preserve per-task capability evidence.
- Capability evidence cites the M7 `routing_resolution_decision`.

## Open Questions

- Capability-class taxonomy: how to compare deepseek-pro vs sonnet vs gpt-5.x against tiers 1-5.
- Whether the gate runs pre-dispatch (refuse), post-dispatch (flag/waive), or both.
- Shared waiver model with M5, or capability-specific.
- Default policy when premium is GENUINELY unavailable: block, or warn-and-proceed-on-DeepSeek with recorded debt.

## Constraints

- Build on M0 provenance (model/capability already in the field list) + M5
  transition policy + M6 rollout modes.
- No false-positive deadlocks when premium is legitimately unavailable — that path
  must be a visible, waivable decision, not a hang.
- Keep per-task routing economics (do not force everything premium).
- Do not accept env-var or binary presence as proof of authority to dispatch a model.
- Keep batch evidence granular enough for task-level policy decisions.

## Done Criteria

1. Each complexity-routed dispatch emits a capability `EvidenceRef` with adjudicated tier, actual model, capability class, availability basis, and `routing_resolution_decision` id.
2. Availability is authority-proven against real dispatch auth, not env-var or binary proxies (a CLI-subscription premium route counts as available).
3. A capability gate compares actual model capability against adjudicated tier and flags/blocks sub-tier dispatch per rollout mode, with scoped waivers.
4. Batch-level dispatch preserves per-task capability evidence and cannot hide a sub-tier task.
5. Capability degradations are operator-visible in status/chain/cloud.
6. The finalize->execute tier handoff is covered (assigned tier == checked tier).
7. Tests cover: adequate dispatch; sub-tier dispatch (block/warn/waive); premium-unavailable; CLI-subscription-available-with-no-env-key; env/binary-proxy false availability; batch-level mixed capability; missing `routing_resolution_decision`; and the original silent-degrade scenario as a regression.

## Touchpoints

- finalize -> execute dispatch / routing
- `megaplan/profiles` (tier_models resolution, the model floor)
- `megaplan/runtime/key_pool`, worker availability
- transition policy (M5) + rollout modes (M6)
- M7 `routing_resolution_decision`
- status / chain / cloud surfaces
- routing/capability tests + the silent-degrade regression

## Rubric

- Profile: `partnered`
- Robustness: `thorough`
- Depth: `high`

Rationale: moderate structural novelty (extends M5's capability model) but high
correctness stakes on routing; thorough robustness to cover the false-positive
deadlock risk when premium is unavailable.
