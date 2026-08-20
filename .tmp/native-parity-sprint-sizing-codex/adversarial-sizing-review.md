# Codex Task: Adversarial Review of Native Semantic Parity Sprint Sizing

Working directory: `/Users/peteromalley/Documents/Arnold`

You are the skeptic. Read:

- `docs/arnold/megaplan-native-semantic-parity-master-plan.md`
- `docs/arnold/megaplan-native-parity-existing-work-swarm-synthesis.md`

Your job is to challenge the sprint decomposition. Look for:

- hidden overloading inside "aggressive two-week sprint" labels;
- places where the plan assumes existing code lowers effort but actually only
  creates integration risk;
- places where two adjacent sprints are artificial and can be safely merged;
- places where one sprint must be split to avoid mid-sprint improvisation;
- false-closure risks created by condensing.

You may inspect source/tests to verify claims, but do not edit files.

Hard constraints:

- The end-state is source-authoritative semantic parity, not representational
  parity.
- The known failure mode is agents closing on representational proof.
- Existing execute/override code can reduce implementation effort, but old route
  authority must still be dead-deleted or fenced.
- S7 cannot be treated as pure final assembly if required scripts are unbuilt.

Output format:

1. Overall sizing verdict.
2. Sprints that are too large.
3. Sprints that can be merged.
4. Sprints that must not be merged.
5. A recommended spine, if different from the current one.
6. For every sprint in that recommended spine, a short reason why it is or is not
   truly a two-week sprint.

Be direct. Keep it under 1800 words.
