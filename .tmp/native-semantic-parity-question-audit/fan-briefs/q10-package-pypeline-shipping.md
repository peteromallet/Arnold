# Q10 Audit: `.pypeline` Package Shipping

Working directory: `/Users/peteromalley/Documents/Arnold`

You are an independent DeepSeek subagent. Do not modify files.

Read `docs/arnold/megaplan-native-semantic-parity-master-plan.md`, then answer this question only:

Does `.pypeline` source actually ship in the built package? Check package data/manifest config and any existing wheel/sdist artifacts if present.

Plan assumption tested: checker `--mode installed-package` can inspect source.

If the answer is bad: fix packaging in S1a, or installed-package mode silently checks nothing.

Return:
- Verdict: agrees | weakens | contradicts the plan.
- Evidence: exact file:line citations and commands run.
- Smallest concrete plan amendment if needed.
- Keep under 900 words.
