First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: the plan STATE model & on-disk persistence

This is arguably THE foundation — the unified executor must own one coherent state-write
model, and the brief admits there's no `schema_version`, ~30 scattered `save_state_merge_meta`
sites, a 3-key allowlist bridge, and a "split-ownership" disk-merge. Go deeper than the brief.

Investigate (read the real code, cite path:line):
- `state.json` shape and every place it's read/written. Start: `save_state_merge_meta`
  (`shared.py` ~355 and the other ~29 sites), `inprocess_step.py:85-88` allowlist diff,
  the executor's `_merge_state_to_disk` split-ownership merge, `types.py:26-28` state_patch.
- What is the actual schema of `state.json`? Is there ONE authoritative definition or is it
  implicit/ad-hoc dict mutation everywhere? Are keys (`current_state`, `next_step`, `iteration`,
  `last_gate`, `meta`, `history`, `plan_versions`, `sessions`, `resume_cursor`, `active_step`,
  `awaiting_user`...) documented/typed anywhere, or just sprinkled?
- Concurrency / atomicity: are writes atomic (tmp+rename) or can a crash mid-write corrupt
  state? Any file locking? What happens with two processes (auto shells subprocesses)?
- Is `meta` a dumping ground? Counters read by gate/tiebreaker — typed or magic strings?

Key question: is the state model coherent enough to become the single source of truth the
unified executor owns, or is it an ad-hoc accreted dict that needs a real schema + atomic
write discipline FIRST? Find corruption/race/consistency hazards the brief did NOT name.
