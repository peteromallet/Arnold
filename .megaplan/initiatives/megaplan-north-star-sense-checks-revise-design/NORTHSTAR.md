# North Star: Megaplan North Star Sense Checks in Revise

The goal is to make explicit North Star sense-check questions actionable inside
Megaplan's plan/gate/revise/review loop.

Done means Megaplan can carry a bad or unclear North Star sense-check answer as a
structured `north_star_action`, route that action into revise, require revise to
make concrete plan changes or halt, and prevent unresolved blocking actions from
being treated as closeout-ready narrative.

The implementation must preserve the design in
`docs/arnold/megaplan-north-star-sense-checks-revise-design.md`:

- Questions are explicitly defined in `NORTHSTAR.md` and/or sprint briefs.
- Questions inform plan and critique, but enforceable blockers are created by
  gate/review and carried into revise as structured actions.
- Revise addresses actions by changing the plan, adding gates, adding scenarios,
  adding checker/dead-delete requirements, or halting when unmappable.
- Dangerous categories are blocking by schema rule, not by agent judgment:
  route authority, baselines, row/carrier exemptions, target narrowing,
  generated conformance authority, and live-plan topology/resume risk.
- Explanation-style checks must support clean-context review. The executor's own
  closeout narrative is not sufficient evidence.
- `north_star_critical: true` must be a real chain/milestone field and must be
  rejected for robustness modes that skip the enforcing phases.

This sprint is not allowed to implement native semantic parity extraction. It is
only the Megaplan runner/planning machinery needed so future semantic-parity
sprints can be reviewed and revised against their North Star.

Closure standard:

- Tests prove `north_star_actions` flow from gate/carry into revise.
- Tests prove revise either records concrete addressed actions with plan refs or
  halts on unmappable/human-halt blocking actions.
- Tests prove schema-assigned blocking severity cannot be downgraded.
- Tests prove `north_star_critical` rejects incompatible robustness modes.
- Tests prove review/finalize cannot close unresolved blocking North Star
  actions as prose-only completion.
- Megaplan skill/docs are updated so future agents know where questions are
  defined and how actions are enforced.
