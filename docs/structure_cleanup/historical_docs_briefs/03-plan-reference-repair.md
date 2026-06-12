You are auditing references to docs/plans files before any move.

Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task:
- Search for references to docs/plans/plan_v2.md, docs/plans/revised_plan.md, docs/plans/finalize.json, docs/plans/loose-work-consolidation-plan.md, and bare names plan_v2.md, revised_plan.md, finalize.json.
- Exclude docs/structure_cleanup/* and docs/megaplan_chains/* unless they reveal active guidance.
- For each reference, classify it as active code/doc guidance, historical evidence, generated/audit evidence, or unrelated.
- If a docs/plans file moves to docs/historical/, give exact reference changes needed.

Constraints:
- Do not edit files.
- Be conservative with code comments: changing a reference in code is allowed only if the target path actually moves.
- Output a reference repair map.
