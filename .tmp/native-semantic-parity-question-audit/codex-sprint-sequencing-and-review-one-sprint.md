You are Codex acting as an independent extra-high-reasoning planning reviewer. Work in `/Users/peteromalley/Documents/Arnold`. Read-only: do not edit files.

The user wants a precise answer to this question:

1. For `docs/arnold/megaplan-native-semantic-parity-master-plan.md`, what is the right aggressive two-week sprint breakdown after all vetting so far? Include the actual North Star sense-check questions that should be attached to each sprint.
2. Separately, for `docs/arnold/megaplan-north-star-sense-checks-revise-design.md`, make the review/revise North Star actions mechanism fit into ONE sprint. Do not inflate it into a multi-sprint roadmap. Identify exactly what belongs in that one sprint and what is follow-up/out of scope.

Read first:
- `docs/arnold/megaplan-native-semantic-parity-master-plan.md`
- `docs/arnold/megaplan-north-star-sense-checks-revise-design.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `docs/arnold/gpt55-native-parity-endstate-gap-report.md` if present

Important context:
- The native semantic parity plan has been revised many times. It now includes S0 runner/North Star action plumbing, S1a checker authority, S1b-1 runtime substrate proof, S1b-2 builder slice, then S2-S7 extraction/final rollout.
- Prior review said expected size is roughly 13-15 lean two-week sprints after vetting; the missing substrate is real, so this may require splitting some broad milestones further.
- The North Star action/revise mechanism itself should be ONE aggressive sprint. Do not call it five sprints. The previous accidental five-sprint roadmap was overexpanded.
- We want the sprint breakdown to be practical: aggressive but not fake-compressed. Split overloaded milestones where necessary. Keep scope coherent and testable.

Output format:
1. Verdict: is the current master plan sequencing broadly right, overloaded, or missing sequencing?
2. Proposed native semantic parity sprint list: each sprint should have label, two-week objective, scope, hard exit gates, and 3-6 North Star sense-check questions.
3. Identify which existing master-plan milestones should be split or merged.
4. One-sprint scope for the North Star review/revise mechanism: exact deliverables, exit gates, and what is explicitly follow-up/out of scope.
5. Any document edits you recommend, with concise patch-level guidance.

Be opinionated. Keep under 2200 words. Use file references when they matter, but do not drown in citations.
