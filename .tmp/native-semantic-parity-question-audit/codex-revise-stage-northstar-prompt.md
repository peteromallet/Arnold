You are Codex acting as an independent high-reasoning design reviewer. Work in
`/Users/peteromalley/Documents/Arnold`. Read-only: do not edit files.

Focus narrowly on the Megaplan REVISE stage.

We already got a broad recommendation: North Star sense checks should be
structured inputs across plan/critique/gate/finalize/review. The user clarified
the key question: how should this fit into the Megaplan revise stage specifically,
so a critique/gate/review finding like "this plan does not satisfy the North
Star" becomes concrete plan changes, exit gates, tests, tasks, or halt actions.

Read:
- `docs/arnold/megaplan-native-semantic-parity-master-plan.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`
- Megaplan revise implementation and prompts under `arnold_pipelines/megaplan/`
  (`handlers/revise.py`, `prompts/revise.py`, `schemas/runtime.py`, gate/critique
  handoff code, finalize handoff code, and any tests you find).

Answer:
1. Where exactly does revise receive critique/gate/review findings today?
2. What minimal schema should represent a North Star sense-check action passed to
   revise?
3. How should revise apply those actions to a plan: add plan item, add exit gate,
   add scenario/test, add checker row, add dead-delete test, add human halt,
   escalate robustness, reject closeout, etc.?
4. What should revise refuse to do? For example, when should it halt instead of
   silently rewriting the plan?
5. How would this interact with existing revise loop caps/no-progress behavior?
6. What is the smallest implementation slice and tests?

Output under 1200 words. Be concrete and cite file:line evidence.
