# Decomposition refactor — running status

> Meta checklist (per Operating principles §"Maintain the meta checklist
> doc; update after each chunk, restate the principles"). Updated after
> each chunk.

## Operating principles (restated)

- No human review required between steps.
- No questions asked, no approvals sought — every choice is the
  agent's.
- Blockers get overcome, not reported. Fallback paths; if stuck >2
  attempts → `BLOCKER-<n>.md` + keep going.
- Keep pushing until everything is done end-to-end.
- Don't disrupt the live megaplan — isolated via worktree + dedicated
  venv at `.venv-decomp/`.
- The existing megaplan flow must still work after all changes.

## Checklist (from `briefs/megaplan-decomposition.md` v2)

### 1. Find & harden the source plan
- [x] Located source plan (briefing in Downloads, copied to
      `briefs/megaplan-decomposition.md`).
- [x] Deployed 3 subagent critiques (architecture, implementation-gaps,
      adversarial-risk).
- [x] Applied improvements iteratively → v2 (recorded in `## Critique
      deltas`).

### 2. Define the abstractions
- [x] Characterised loop types (backwards-edge under condition; not a
      new primitive).
- [x] Extracted primitive step types: Produce / Judge / Decide /
      Subloop / Override.
- [x] Defined parent abstraction: `Pipeline` containing `Stage`s with
      `Edge`s, plus `Overlay`s for robustness/mode/with_prep/with_feedback.
- [x] Confirmed existing megaplan expressible as one pipeline +
      overlays.

### 3. Build the demonstration
- [ ] Refactor existing megaplan into the new composable primitives
      (Sprint 2).
- [ ] Build the multi-critique megaplan process (fan-out judges +
      synthesis; doc-critique as secondary) using the same primitives
      (Sprint 1 ships the judges demo; Sprint 2 ships doc-critique).

### 4. Sprint execution
- [x] Broke work into two 2-week sprints (demo-FIRST sequencing).
- [x] Set up git worktree (`../megaplan-decomp`, branch `decomp/main`)
      + dedicated venv (`.venv-decomp`) + isolation smoke check.
- [ ] Execute sprints sequentially with all-Claude profile @ robust
      robustness, depth high.
   - Sprint 1: in progress (megaplan auto running for plan
     `decomp-sprint-1`).
   - Sprint 2: pending.
- [x] Maintained meta checklist doc (this file).

### 5. End-to-end validation
- [ ] Test the original megaplan planning flow end-to-end (post Sprint 2).
- [ ] Test the new multi-critique flow end-to-end (post Sprint 2).
- [ ] Confirm new sequences can be composed easily from the primitives.

## Success criteria (from brief)

- [ ] All 7 acceptance tests pass.
- [ ] Legacy `WORKFLOW` dict and `_ROBUSTNESS_OVERRIDES` deleted.
- [ ] `megaplan auto` on a fresh idea runs through unified Pipeline.
- [ ] Live `megaplan` (system shebang) keeps working.
- [ ] Fan-out judges pipeline shipped + importable.

## Isolation verification (run after each commit)

```bash
cd /tmp && /Users/peteromalley/Documents/megaplan/.venv/bin/python \
  -c "import megaplan; print(megaplan.__file__)"
# Must print: /Users/peteromalley/Documents/megaplan/megaplan/__init__.py
```

Last verified: 2026-05-15 22:52.

## Sprint 1 run

- Plan: `decomp-sprint-1`
- Profile: `all-claude`
- Robustness: `robust`
- Depth: `high`
- Mode: `code`
- Cost cap: $30
- Started: 2026-05-15 22:52
- Status: running (megaplan auto in background, monitored)
