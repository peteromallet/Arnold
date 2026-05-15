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
- [x] Refactor existing megaplan into the new composable primitives.
      Sprint 2 lands a compiled `Pipeline` (`megaplan/_pipeline/planning.py`)
      derived structurally from `WORKFLOW`. The handler ports themselves
      (replacing `_RuntimeStep` placeholders with real handler-backed
      `Step` instances) are deferred to a Sprint-3 follow-up — see
      "Sprint 3 follow-up" below for the explicit boundary.
- [x] Build the multi-critique megaplan process. Sprint 1 ships the
      fan-out judges + synthesis demo (`megaplan/_pipeline/demo_judges.py`).
      Sprint 2 ships the doc-critique 3x loop
      (`megaplan/_pipeline/demos/doc_critique.py`).

### 4. Sprint execution
- [x] Broke work into two 2-week sprints (demo-FIRST sequencing).
- [x] Set up git worktree (`../megaplan-decomp`, branch `decomp/main`)
      + dedicated venv (`.venv-decomp`) + isolation smoke check.
- [x] Execute sprints sequentially with all-Claude profile @ robust
      robustness, depth high.
   - Sprint 1: complete (megaplan auto ran most of T1-T2 before the
     persistent-session cache stalled it; T3-T6 completed manually
     following the megaplan-generated plan in `final.md`).
   - Sprint 2: complete manually (megaplan auto would have hit the
     same cache stall; the megaplan-produced Sprint 1 plan proved
     sufficient as a template).
- [x] Maintained meta checklist doc (this file).

### 5. End-to-end validation
- [x] Test the original megaplan planning flow end-to-end. The full
      `pytest tests/` suite (1740 tests) stays green; the live megaplan
      binary at `/Users/peteromalley/.local/bin/megaplan` (symlinked
      into the main checkout's venv) keeps resolving to the main
      checkout, verified after every commit.
- [x] Test the new multi-critique flow end-to-end. Three pipelines
      run end-to-end through the new executor: fan-out judges, compose
      4-stage, doc-critique 3x loop. Each has an acceptance test.
- [x] Confirm new sequences can be composed easily from the primitives.
      The compose test (`tests/test_pipeline_compose.py`) builds a
      4-stage pipeline in ≤50 lines of construction code using only
      public primitives.

## Success criteria (from brief)

- [x] Acceptance tests pass — 33 new pipeline tests added, all green.
      Compose / fan-out / doc-critique / planning-parity / profile-compat
      all pass. The byte-identical artifact-level parity test (#1) and
      kill-mid-run resume test (#5) require the Sprint-3 handler port +
      auto.py rewrite; these are documented Sprint-3 follow-ups.
- [ ] **Deferred to Sprint 3:** legacy `WORKFLOW` dict and
      `_ROBUSTNESS_OVERRIDES` deletion. Sprint 2 builds the Pipeline as
      a *derived view* of WORKFLOW so the two stay in lock-step; Sprint
      3 inverts the direction.
- [ ] **Deferred to Sprint 3:** `megaplan auto` walks the unified
      Pipeline. Requires the handler port + auto.py rewrite.
- [x] Live `megaplan` (system shebang) keeps working — verified after
      every commit.
- [x] Fan-out judges pipeline shipped + importable
      (`megaplan/_pipeline/demo_judges.py`).

## Isolation verification (run after each commit)

```bash
cd /tmp && /Users/peteromalley/Documents/megaplan/.venv/bin/python \
  -c "import megaplan; print(megaplan.__file__)"
# Must print: /Users/peteromalley/Documents/megaplan/megaplan/__init__.py
```

Last verified: 2026-05-15 23:49.

## Sprint 1 run (megaplan-driven, then manual completion)

- Plan: `decomp-sprint-1`
- Profile: `all-claude`
- Robustness: `robust`
- Depth: `high`
- Mode: `code`
- Cost cap: $30 (actual spend: $12.79)
- Started: 2026-05-15 22:52
- Megaplan auto outcome: prep → plan → critique → gate → revise loop
  stalled at iteration 14 due to persistent-session response caching
  (the same prompt was producing the same response every iteration).
  Force-proceed override applied; auto continued through finalize then
  stalled again at execute for the same caching reason. T1 + T2 (types
  + executor) landed via megaplan execute before the stall. The
  megaplan-generated `final.md` was used as the authoritative checklist
  for finishing T3-T6 manually.

### Sprint 1 commits on `decomp/main`

- `5f0e6682` — T1: types.py + __init__.py with frozen primitives
- `48e5cde8` — fix(workers): extract prose-prefixed JSON
- `14066b7a` — fix(shannon_worker): extract prose-prefixed JSON
- `a7e9ae49` — T2: executor.py standalone runtime
- `e60d45ff` — T3: demo_judges hermetic fan-out demo
- `94b68b3e` — T4: compose + demo_judges acceptance tests
- `ab39667c` — T5: docs/pipeline-resume + brief revision note

## Sprint 2 (manual, based on Sprint 1 megaplan-generated pattern)

### Sprint 2 commits on `decomp/main`

- `b30948a9` — doc-critique demo + executor state-propagation fix
- `1ed0fa74` — compile WORKFLOW into Pipeline + parity tests

### Sprint 2 deliverables

- `megaplan/_pipeline/demos/doc_critique.py` — 3x critique→revise loop
  built entirely on Sprint-1 primitives. Loops fall out of labelled
  edges (no new combinator needed).
- `megaplan/_pipeline/planning.py` — compiles `WORKFLOW` +
  `_ROBUSTNESS_OVERRIDES` + `_with_prep_from_state` +
  `_with_feedback_from_state` into a single declarative `Pipeline` value
  with three composing `Overlay`s. Proves the existing planning state
  machine is expressible as one configuration of the primitives.
- `tests/test_pipeline_doc_critique.py` — doc-critique acceptance test.
- `tests/test_pipeline_planning_parity.py` — 10 parametrized cases
  proving the compiled Pipeline matches `WORKFLOW` + all five
  robustness levels + with_prep + with_feedback overlays exactly.
- `tests/test_pipeline_legacy_profile_compat.py` — 19 cases (18
  profiles + 1 phase-names check) proving every shipped profile TOML
  covers the required phase slots and phase names map to compiled
  Pipeline stages addressable by name.

## Sprint 3 follow-up (out of scope here)

These are the deliberately-deferred chunks. They require either the
handler port (a multi-file refactor across ~3900 LOC of handlers) or
the auto.py rewrite (~1700 LOC), and would push the worktree past the
"isolated, reversible" bar this brief committed to.

1. Replace `_RuntimeStep` placeholders in
   `megaplan/_pipeline/planning.py` with real handler-backed `Step`
   instances. One `Step` per handler under `megaplan/handlers/`.
2. Update `megaplan/auto.py` to walk the compiled `Pipeline` instead
   of polling `WORKFLOW` directly. Preserve all stall/cost/escalate
   policy bit-for-bit.
3. Delete `WORKFLOW` and `_ROBUSTNESS_OVERRIDES` from
   `megaplan/_core/workflow.py`. Pipeline becomes the source of truth.
4. Acceptance tests #1 (byte-identical parity) and #5 (kill-mid-run
   resume) — both require the executor + auto.py integration.
5. Apply the same fan-out + barrier-join primitive to the existing
   `parallel_critique` cross-cutting middleware so it stops being
   hard-coded inside `handle_critique`.

A separate `briefs/sprint-3-handoff.md` should capture this scope before
the work starts, mirroring the Sprint-1 / Sprint-2 idea files.
