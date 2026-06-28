# North Star — God-file splits epic

This document is the north star for the whole epic. It says what "working well" means and
when the epic is done. The three milestone briefs (`m1.md`, `m2.md`, `m3.md`) are the
per-sprint scope; this is the outcome they sum to.

## What I'm actually doing

Finishing the structural-decomposition epic's unfinished work: decompose the three remaining
god-files in the porting / agent layers into focused submodules (~<=600-700 LOC each) with the
**public surface byte-for-byte identical** and **behavior proven by the characterization oracle**:

- `vibecomfy/porting/emitter.py` (5129 LOC) — the workflow-Python emitter (m2-emitter left it).
- `vibecomfy/comfy_nodes/agent/edit.py` (7236 LOC) — the agent-edit handler (m5-agent-edit left it).
- `vibecomfy/porting/edit/apply.py` (3009 LOC) — the edit-application pipeline.

## What "working well" means

- No god-file > ~700 LOC remains in the `vibecomfy/porting/` or `vibecomfy/comfy_nodes/agent/`
  layers after the epic. Each was decomposed by seam into cohesive submodules with a thin
  facade preserving the public import path.
- Every public symbol that existed before the epic is importable from the same path after it
  (`python -c "import vibecomfy"` + full `__all__` traversal green at every milestone).
- Emitted workflow Python is byte-identical (characterization emitter snapshots unchanged);
  agent-edit + edit-apply behavior unchanged (their suites green).
- `.importlinter` (ir-core-no-porting contract) green; `make check` green end-to-end at every
  milestone.
- No new circular imports or broken re-exports were introduced (the topological-risk rule: the
  planner reasons explicitly about the import graph because a designed-in cycle stops the suite
  collecting and the oracle can't catch it).

## Done when

- m1, m2, m3 each landed on `worktree-phase2-reorg` (stacking on the phase-2 reorg), each with
  `make check` green and the relevant behavior gate byte-identical / no new failures.
- The three god-files are thin facades (or gone); no submodule exceeds ~700 LOC.
- A final `make check` on the stacked branch is green; the characterization oracle shows no
  regressions vs the 7-failure/15-pass baseline.

## Anti-scope

- Do NOT change emitted workflow output, the agent-edit contract/wire-format/UI, or
  edit-application outcomes. This is pure structural decomposition, behavior-preserving.
- Do NOT rename or move public symbols. The public import surface is frozen.
- Do NOT touch the characterization goldens except to confirm they are unchanged.
- Each milestone stays in its own file(s); don't let one milestone's split bleed into another's
  god-file.
