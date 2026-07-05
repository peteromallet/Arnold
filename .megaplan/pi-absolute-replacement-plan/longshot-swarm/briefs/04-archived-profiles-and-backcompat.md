Working directory: /Users/peteromalley/Documents/Arnold

Task: Look in archived docs/plans/profiles for profile syntax and old run artifacts that the migration might unexpectedly need to read or preserve.

Focus areas:
- docs/archive/**
- .megaplan/plans/** profile/run artifacts, but avoid dumping huge logs; sample and search targeted strings
- docs/foundation-audit/FOUNDATION_07-profiles.md
- tests/profiles, tests/arnold/pipeline/*profiles*

Question: Are archived profiles/run artifacts an external compatibility surface or only historical data?

Output:
- Findings with paths and judgment.
- Recommended plan additions around historical readability, rejection deadlines, or migration tooling.
- Keep under 800 words.
