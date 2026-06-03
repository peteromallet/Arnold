# M5: Full Transition Validator, Chain Provenance, and Capability Trust

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Extend the transition policy/writer model to the full authority-increasing routing surface, while making chain/worktree/cloud/CI evidence SHA-pinned and worker capability part of evidence trust.

## Scope

IN:

- Extend `TransitionPolicy` / `TransitionDecision` / `TransitionWriter` to:
  - `review -> execute`
  - chain milestone advancement
  - PR-ready / PR-merged / chain-complete advancement where used
  - recovery paths that promote blocked/partial execution
  - force-proceed / override paths
- Treat overrides as scoped waivers with actor/source, reason, affected evidence refs, scope, expiry/retry policy, and durable decision record.
- Capture `git_base_ref` at milestone start.
- Propagate declared chain base branch into evidence collection.
- Diff `base..HEAD` for committed milestones.
- Account for preexisting dirty paths.
- Pin CI/check evidence to commit SHA and run/check id.
- Add pre-dispatch worker capability checks for phases requiring evidence capabilities.
- Emit canonical denial detail, e.g. `transition_denial.json` or equivalent event.

OUT:

- Do not flip global enforcement default-on.
- Do not remove legacy shortcuts until typed evidence covers the route.
- Do not solve all sandbox hardening beyond evidence capability trust.

## Locked Decisions

- Authority-increasing state writes go through `TransitionWriter`.
- Overrides are waivers, not bypasses.
- Chain/cloud evidence cannot rely on branch names or clean working trees alone.
- Incompetent or tool-limited worker fallback cannot silently produce complete objective evidence.

## Open Questions

- Exact route list and ordering for migration to `TransitionWriter`.
- Where to store chain/milestone evidence base refs.
- Policy for fallback when required worker capability is unavailable.
- How cloud/resident status should classify and surface transition denials.

## Constraints

- Preserve resumability and chain state safety.
- Avoid infinite re-execute/re-init loops; distinguish retryable and non-retryable denials.
- Keep denials operator-visible.

## Done Criteria

1. Full authority-increasing route list is covered by policy/writer or explicitly documented as deferred.
2. Chain milestone advancement uses SHA-pinned evidence.
3. CI evidence is commit/run pinned.
4. Overrides produce scoped waiver decisions.
5. Worker fallback cannot silently lose required evidence capability.
6. Transition denials are structured and visible.
7. Tests cover chain committed work, carried dirty paths, overrides, recovery, capability fallback, and non-retryable denial.

## Touchpoints

- `megaplan/auto.py`
- `megaplan/handlers/review.py`
- `megaplan/handlers/execute.py`
- `megaplan/handlers/override.py`
- `megaplan/_core/workflow.py`
- `megaplan/chain/__init__.py`
- `megaplan/cloud/*`
- worker routing/capability modules
- transition, chain, cloud, override, and worker tests

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: widest blast radius and highest false-positive risk.

