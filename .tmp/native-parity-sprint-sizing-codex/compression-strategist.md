# Codex Task: Native Semantic Parity Sprint Compression Review

Working directory: `/Users/peteromalley/Documents/Arnold`

You are reviewing the sprint structure in:

- `docs/arnold/megaplan-native-semantic-parity-master-plan.md`
- `docs/arnold/megaplan-native-parity-existing-work-swarm-synthesis.md`

Task:

Assess whether the current 15-sprint aggressive two-week spine can be safely
condensed now that the plan has identified reusable existing work. Be concrete
and opinionated.

Read the two docs above. Then inspect local code only where needed to verify
claims about existing work. Do not edit files.

Questions to answer:

1. Which sprints, if any, can be merged without recreating the false-pass risk?
2. Which sprints must remain separate despite existing scaffolding?
3. Where does existing implementation genuinely reduce calendar/sprint count,
   versus only reducing risk inside the same sprint?
4. Is the current 15-sprint spine appropriate, over-split, or under-split?
5. Propose a revised sprint spine if you recommend changes.
6. For each sprint in your proposed spine, explain why it is an aggressive but
   plausible two-week sprint.

Constraints:

- Do not recommend merging checker/carrier reconciliation with extraction unless
  you can explain why the historical false-pass pattern cannot recur.
- Do not treat old representation/conformance ledgers as proof.
- Keep S0 North Star/revise plumbing to one sprint unless you have evidence it is
  impossible.
- Consider execute and override existing work from the swarm: these may be
  hardening/extraction sprints rather than greenfield builds.

Output format:

- Verdict: one paragraph.
- Proposed sprint spine table with columns: Sprint, Keep/Merge/Split, Reason,
  Two-week rationale.
- Condensation opportunities.
- Non-negotiable separations.
- Open risks.

Keep it under 1800 words.
