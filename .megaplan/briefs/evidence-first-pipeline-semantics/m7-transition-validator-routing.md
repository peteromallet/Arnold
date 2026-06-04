# M7: Transition Validator Routing

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Extend the transition policy/writer model to the full authority-increasing routing surface, while making chain/worktree/cloud/CI evidence SHA-pinned and worker capability part of evidence trust.

Fold config routing into the validator: routing is recomputed from pinned inputs, never frozen. The pinned inputs are the adjudicated tier, task id, policy, and profile; the tier-to-model map is recomputed from current capability. Each resolution emits a `routing_resolution_decision`, and stale decisions are rejected through lease/lock plus compare-and-swap discipline.

## Scope

IN:

- Extend `TransitionPolicy` / `TransitionDecision` / `TransitionWriter` to:
  - `review -> execute`
  - chain milestone advancement
  - PR-ready / PR-merged / chain-complete advancement where used
  - recovery paths that promote blocked/partial execution
  - reset/reconcile routes
  - config-reroute routes
  - force-proceed / override paths
- Treat overrides as scoped waivers with actor/source, reason, affected evidence refs, scope, expiry/retry policy, and durable decision record.
- Capture `git_base_ref` at milestone start.
- Propagate declared chain base branch into evidence collection.
- Diff `base..HEAD` for committed milestones.
- Account for preexisting dirty paths.
- Pin CI/check evidence to commit SHA and run/check id.
- Add pre-dispatch worker capability checks for phases requiring evidence capabilities.
- Recompute routing from pinned inputs: adjudicated tier, task id, policy, and profile stay pinned; tier-to-model maps are recomputed.
- Emit `routing_resolution_decision` for recompute, reroute, honor-stale, and waiver outcomes.
- Reject frozen routing maps such as stale `tier_models` on resume unless an explicit decision records why they were honored.
- Add concurrency and TOCTOU controls: lease/lock, compare-and-swap on checked inputs, and stale-decision rejection.
- Emit canonical denial detail, e.g. `transition_denial.json` or equivalent event.

OUT:

- Do not flip global enforcement default-on.
- Do not remove legacy shortcuts until typed evidence covers the route.
- Do not solve all sandbox hardening beyond evidence capability trust.
- Do not re-resolve plan content; only routing/capability layers are recomputed.
- Do not freeze tier-to-model maps into durable truth.

## Locked Decisions

- Authority-increasing state writes go through `TransitionWriter`.
- Overrides are waivers, not bypasses.
- Chain/cloud evidence cannot rely on branch names or clean working trees alone.
- Incompetent or tool-limited worker fallback cannot silently produce complete objective evidence.
- Routing/capability config is recomputed from pinned inputs; frozen `tier_models` must not survive resume as authority.
- Transition and routing decisions are valid only for the checked inputs they record.

## Open Questions

- Exact route list and ordering for migration to `TransitionWriter`.
- Where to store chain/milestone evidence base refs.
- Policy for fallback when required worker capability is unavailable.
- How cloud/resident status should classify and surface transition denials.
- Exact boundary between pinned plan decisions and recomputed routing/capability config.
- Lease scope and timeout behavior for concurrent driver/cloud operations.

## Constraints

- Preserve resumability and chain state safety.
- Avoid infinite re-execute/re-init loops; distinguish retryable and non-retryable denials.
- Keep denials operator-visible.
- Re-resolution must be deterministic given the same pinned inputs and current capability.
- Compare-and-swap failures must fail closed with stale-decision diagnostics.

## Done Criteria

1. Full authority-increasing route list is covered by policy/writer or explicitly documented as deferred.
2. Chain milestone advancement uses SHA-pinned evidence.
3. CI evidence is commit/run pinned.
4. Overrides produce scoped waiver decisions.
5. Worker fallback cannot silently lose required evidence capability.
6. Routing is recomputed from pinned adjudicated tier/task id/policy/profile inputs, with the tier-to-model map recomputed from current capability.
7. Every routing recompute, reroute, honor-stale, or waiver emits a `routing_resolution_decision`.
8. Resume rejects stale/frozen routing maps unless a durable decision explicitly honors them.
9. Transition/routing decisions are fenced by lease/lock and compare-and-swap on checked inputs.
10. Stale-decision rejection is structured and visible.
11. Transition denials are structured and visible.
12. Tests cover chain committed work, carried dirty paths, overrides, recovery, reset/reconcile routing, config reroute, capability fallback, non-retryable denial, concurrent stale decision, and the frozen-`tier_models`-must-not-survive-resume regression.

## Touchpoints

- `megaplan/auto.py`
- `megaplan/handlers/review.py`
- `megaplan/handlers/execute.py`
- `megaplan/handlers/override.py`
- `megaplan/_core/workflow.py`
- `megaplan/_core/state.py`
- `megaplan/chain/__init__.py`
- `megaplan/cloud/*`
- `megaplan/profiles`
- worker routing/capability modules
- state locks / lease helpers
- transition, chain, cloud, override, config-reroute, concurrency, and worker tests

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: widest blast radius and highest false-positive risk, now including recovery routes, routing recompute, and concurrency/TOCTOU correctness.

