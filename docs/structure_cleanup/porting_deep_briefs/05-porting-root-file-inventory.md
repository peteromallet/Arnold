# Porting Deep Audit 05 — Root File Inventory

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: inventory every remaining root-level file directly under `vibecomfy/porting/` and decide whether it earns root placement.

Focus command:
`find vibecomfy/porting -maxdepth 1 -type f -name '*.py' | sort`

For each file:
1. Classify as public barrel, core workflow, implementation, shim/duplicate, stale/dead, or misplaced.
2. Identify active importers.
3. Recommend delete/move/keep.
4. Flag likely quick wins.

Return a table with evidence and a prioritized action batch.

Do not edit files.
