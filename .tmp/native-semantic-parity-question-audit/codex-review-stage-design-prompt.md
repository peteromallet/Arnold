You are Codex acting as an independent high-reasoning design reviewer. Work in
`/Users/peteromalley/Documents/Arnold`. Read-only: do not edit files.

Task: think through how to add North Star sense-check questions to the Megaplan
Make-A-Plan review stage so each sprint/plan can be checked against its desired
end-state, and so answers create concrete actions rather than just prose.

Read these first:
- `docs/arnold/megaplan-native-semantic-parity-master-plan.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`
- `docs/arnold/megaplan-native-representation-report.md`
- Relevant Megaplan/Make-A-Plan implementation files you discover under
  `arnold_pipelines/megaplan/`, especially planning, critique, review, gate,
  brief generation, schema, and prompt/template code.

Context:
The master plan has been updated to a hybrid lean posture. It keeps core
programmatic controls but uses a `Sprint Review / North Star Sense Check`
section to replace overbroad governance. The desired behavior is not just asking
questions; bad answers must become actions: revise plan, add a test/gate, add a
row, add a carrier mapping, halt-and-ask, or escalate to full apparatus.

Questions to answer:
1. Where in the current Make-A-Plan process should these sense-check questions
   live: plan drafting, critique, revise, gate, review, closeout, or multiple
   places? Be precise about files/modules.
2. What data model/schema should represent a sense-check question, answer,
   verdict, evidence, and resulting action?
3. What are the minimum action types needed? For example: add plan item, add
   exit gate, add scenario, add checker row, add dead-delete test, mark human
   halt, escalate robustness, reject closeout.
4. How should the review stage decide between "non-blocking note", "revise plan",
   "halt-and-ask", and "fail closeout"?
5. How should this fit without making every plan heavyweight? Propose defaults
   for ordinary plans vs North-Star-critical epics like native semantic parity.
6. Can the questions be generated from a North Star document, or should they be
   explicit YAML/markdown inputs? Recommend the first implementation path.
7. What tests/fixtures would prove this works and prevent it from becoming
   narrative-only proof?
8. What is the smallest useful implementation slice?

Output format:
- Verdict first: where to hook it and whether this is worth doing.
- Proposed architecture with concrete files/functions likely to change.
- Proposed schema.
- Action routing rules.
- Minimal implementation slice and tests.
- Risks and what not to build yet.

Be opinionated and practical. Keep under 1600 words. Use file:line citations for
important claims.
