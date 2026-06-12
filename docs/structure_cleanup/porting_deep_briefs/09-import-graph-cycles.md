# Porting Deep Audit 09 — Import Graph And Cycles

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: inspect whether the current porting package structure creates cycles, heavy imports, or awkward root dependencies that motivate moves/deletions.

Focus:
- `vibecomfy/porting/`
- `vibecomfy/ingest/`
- `vibecomfy/workflow.py`
- `vibecomfy/schema/`
- command imports

Questions:
1. Which root-level porting modules are dependency hubs?
2. Which imports cross layers in the wrong direction?
3. Would moving/deleting any remaining files simplify import direction?
4. What can be safely done now?

Return actionable findings, not a broad essay.

Do not edit files.
