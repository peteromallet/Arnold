# Megaplan Decomposition — Meta Checklist & Live Plan

**Status:** in progress. Worktree: `/Users/peteromalley/Documents/.megaplan-worktrees/megaplan-decomposition` on branch `megaplan-decomposition`.
**Source briefing:** `~/Downloads/megaplan-decomposition-briefing.md` (mirrored in `briefs/megaplan-decomposition.md`).
**Driver:** Megaplan `auto`/`chain`, profile `all-claude`, effort `claude:high` for plan/critique/gate, default elsewhere.

## Operating principles (restated every update — non-negotiable)

1. **No human review required between steps.** Sprint boundary is the only natural pause; even there the driver auto-advances if the gate passes.
2. **No questions asked, no approvals sought** — every choice is mine.
3. **Blockers get overcome, not reported.** No excuses, no laziness.
4. **Keep pushing until everything is done end-to-end.**
5. **Don't disrupt the live Megaplan running from this machine.** All work in this worktree; cutover only after all gates pass.
6. **The existing Megaplan flow must still work after all changes** — verified by byte-identical golden artifacts on 3-5 historical plans before promotion.

## Plan critique outcome (3 subagents → consolidated decisions)

The briefing and `briefs/megaplan-decomposition.md` are byte-identical; there is no prior detailed design. Three critique agents reviewed from three perspectives — abstraction design, backcompat/migration risk, sprint feasibility — and converged on the following hardened plan. Issues marked S/M/L by impact.

### Key consolidated findings
- **Abstraction:** the live code's `phase = handler` boundary is an *aggregate*, not a primitive. Decompose into eight primitives (`LLMCall`, `Materialize`, `Critique`, `Revise`, `Gate`, `Tool`, `Loop`, `Branch`). Replace `plan_dir` filesystem assumptions with a `Workspace` and `state.json` shared blob with a `Blackboard`. Workflow becomes a YAML graph the engine reads. Profile maps **role → vendor**, not phase-name → vendor.
- **Backcompat:** single global `~/.local/bin/megaplan` entrypoint means a `pip install -e .` from the worktree would clobber it. Required: dual-CLI install — keep live `megaplan` pinned to main checkout; install worktree as `megaplan-next` via separate `uv tool install` with separate `MEGAPLAN_HOME=~/.megaplan-next` and separate `~/.config/megaplan-next/`. Versioned artifact filenames (`plan_vN.md`, `state.json` etc.) must be preserved as aliases. Resident daemon, `chain`/`auto`/`execute`/`review` processes already running — touched files must not collide.
- **Sprint feasibility:** realistic effort is 12–13 weeks across Sprint 0 + 5 sprints, not the briefing's implicit 6–8. Multi-critique demo is the **falsification sprint** and runs BEFORE the planning refactor — if primitives can't express it, fix the spec, not the refactor.

## Primitive set (frozen for Sprint 1 input)

| Primitive | Inputs | Output | Side effects | Idempotency key |
|---|---|---|---|---|
| `LLMCall` | role, prompt template, inputs, output_schema, model_override? | Payload | pure | `(role, template_hash, inputs_hash, model_id)` |
| `Materialize` | slot, content, format | ArtifactRef | writes_artifact | `(slot, content_hash)` |
| `Critique` | target_ref, checks[], role | CritiqueReport | pure (composed) | derived |
| `Revise` | target_ref, critique_ref, role | NewVersion | writes_artifact | derived |
| `Gate` | inputs[], decision_template, verdict_schema | Verdict | pure | derived |
| `Tool` | command, cwd, env, timeout | ToolOutput | external | none (retry on timeout) |
| `Loop` | body[], until?, max, counter_slot | LoopRecord | engine-managed counter | n/a |
| `Branch` | when_expr, then[], else[] | BranchRecord | pure | n/a |

Every primitive declares: `input_schema`, `output_schema`, `side_effects ∈ {pure, writes_artifact, mutates_state, external}`, `idempotency_key`, `retry_policy`. Engine validates `reads`/`writes`/`emits_signals` at workflow load.

## Parent abstraction (Workflow YAML — frozen for Sprint 1)

```yaml
workflow: doc-critique-3x
inputs: { target_doc: path, focus: str }
roles: { critic: claude, reviser: claude, judge: claude }
nodes:
  - { id: load, type: Materialize, slot: target, from_input: target_doc }
  - id: iter
    type: Loop
    max: 3
    body:
      - { id: crit, type: Critique, target_ref: ${target}, role: critic }
      - { id: rev,  type: Revise,   target_ref: ${target}, critique_ref: ${crit}, role: reviser }
      - { id: chk,  type: Gate,     inputs: [${rev}], role: judge }
    until: chk.verdict.decision == "ready"
outputs: { final: ${target} }
```

Existing planning workflow = same schema with ~18 nodes (prep, plan, critique, gate, revise, finalize, execute, review). Joke mode = `LLMCall(role: comedian) → Critique(role: groucho) → Revise → Materialize`. All three demonstrably express in the same grammar — this is the success criterion.

## Sprint breakdown

### Sprint 0 — Isolation & Baseline (3–5 days)
**DoD:**
- Worktree at `~/Documents/.megaplan-worktrees/megaplan-decomposition` ✓
- Separate venv via `uv tool install --from . megaplan --bin megaplan-next` with `MEGAPLAN_HOME=~/.megaplan-next`, separate `~/.config/megaplan-next/`
- Live `megaplan` confirmed untouched (`ls -l $(which megaplan)` resolves to the main checkout)
- Golden fixtures captured:
  - `tests/golden/planning_golden.jsonl` — recorded all-Claude planning run (idea → final plan)
  - `tests/golden/doc_critique_target.md` — input doc for the multi-critique target run
  - `tests/golden/plan_artifacts_v1/` — copy of 3 representative completed plans for migration tests
- Live-surface inventory script `scripts/live_surfaces_smoke.sh` that touches: `plan`, `prep`, `critique`, `revise`, `gate`, `finalize`, `execute`, `review`, `chain start --dry-run`, `auto --dry-run`, `loop-run --dry-run`, `resident status`, `cloud --help`, `bakeoff --help`, `tiebreaker --help`. Passes today on main; pin output as `tests/golden/cli_help_snapshot.txt`.

**`megaplan plan` idea text:**
> Set up an isolated parallel install of Megaplan as `megaplan-next` for refactoring the harness into composable primitives without disrupting the live `megaplan` CLI on this machine. Capture deterministic golden-run fixtures for the existing planning flow and the target document-critique flow. Snapshot the CLI help surface so the public contract can be regression-tested. Deliverable is the install runbook plus passing baseline tests (`pytest tests/golden/test_baseline.py`).

### Sprint 1 — Loop Taxonomy + Primitive Spec (2 weeks)
**DoD:**
- `docs/primitives.md` characterising 4–6 loop archetypes: `critique→revise`, `plan→execute`, `fanout→tiebreak`, `gate→advance`, `compose→materialize`
- `megaplan/primitives/types.py` with frozen dataclasses for `Step`, `StepResult`, `Workspace`, `Blackboard`, `Workflow`, `LoopController`
- `megaplan/primitives/registry.py` registering the 8 primitive types
- One existing phase (`parallel_critique`) re-expressed as a `Critique` primitive call; runs standalone against `doc_critique_target.md` and produces a critique report whose schema validates
- Workflow YAML loader (`megaplan/workflows/loader.py`) parses and validates a `Workflow`; rejects unknown keys, unresolved refs, primitives with unmet `reads`
- Tests: `tests/primitives/test_*.py` cover each primitive's input/output schema, idempotency, retry behavior

**`megaplan plan` idea:**
> Read the existing Megaplan chain/auto/parallel-critique source under `megaplan/` and produce a frozen primitive specification: dataclasses for Step/StepResult/Workspace/Blackboard, a written taxonomy of loop types, and a working spike that re-runs the existing parallel-critique phase via the new primitive API against the captured `doc_critique_target.md` golden fixture. Include a workflow YAML loader with schema validation. Do not modify legacy code; the new module lives under `megaplan/primitives/`.

### Sprint 2 — Multi-Critique MVP on Primitives (2 weeks) — falsification sprint
**DoD:**
- `megaplan-next critique-doc <path> --workflow workflows/doc-critique-3x.yaml` runs 3× critique → revise loop end-to-end on a markdown doc using only new primitives
- `workflows/doc-critique-3x.yaml` matches the schema above; loaded by the engine
- All three perspectives' critique outputs persisted under a fresh `Workspace` (filesystem backend pointed at a per-run dir under `MEGAPLAN_HOME`)
- Engine emits `final.md` (revised doc) + `critique_v{1,2,3}.json` + `gate_signals_v{1,2,3}.json` (same versioned filenames as legacy planning, for downstream compat)
- Regression test `tests/test_doc_critique_e2e.py` runs against fixture, asserts deterministic exit (max 3 iterations, judge verdict, final length > input length)
- `megaplan-next critique-doc --help` lists the command and matches a snapshot

**`megaplan plan` idea:**
> Build the document-critique Megaplan mode end-to-end using only the new primitive library: 3 parallel `Critique` subagent calls, a `Revise` step, a `Gate` step, a `Loop` controller, and a TOML/YAML pipeline config. Ship as `megaplan-next critique-doc <path>` with a golden-fixture regression test. The legacy `chain.py` MUST NOT be invoked by this command — this sprint is the falsification test for the primitive abstraction. If the abstraction can't express this cleanly, fix the spec, not the refactor.

### Sprint 3 — Refactor Planning Flow onto Primitives, Part A: phases (3 weeks)
**DoD:**
- `chain.py` and `parallel_critique.py` re-expressed as `workflows/planning-allclaude-standard.yaml`
- `megaplan-next plan` produces byte-identical artifacts (`plan_vN.md`, `plan_vN.meta.json`, `critique_vN.json`, `gate_signals_vN.json`, `state.json`, `final.md`) to legacy `megaplan plan` for 2 recorded golden ideas (covered by `tests/golden/planning_golden.jsonl` + a second recorded run)
- Workflow YAML covers all 18 nodes (prep, plan, critique, gate, revise×N, finalize)
- Legacy `chain.py` retained behind feature flag `MEGAPLAN_LEGACY_CHAIN=1` for rollback
- Resident daemon adapter: `megaplan/resident/_compat.py` shims old function signatures so resident is unaffected
- Profile system extended: `[profiles.<name>.workflow]` table optional; if unset, falls back to legacy chain. Existing `[profiles.all-claude]` keys preserved as role-mapping shortcuts.

**`megaplan plan` idea:**
> Re-express the existing planning chain (`chain.py` + `parallel_critique.py` + the auto-driver in `auto.py`) as a workflow YAML over the new primitives, covering the all-Claude standard profile end-to-end. The new `megaplan-next plan <idea>` MUST produce byte-identical artifacts to legacy `megaplan plan` for the captured golden runs (verified by `tests/test_planning_artifact_compat.py`). Keep `chain.py` callable behind `MEGAPLAN_LEGACY_CHAIN=1` for rollback. Add a resident-daemon shim that preserves the old per-function call signatures.

### Sprint 4 — Refactor Part B: execute, receipts, editorial, tickets (3 weeks)
**DoD:**
- `execute/`, `receipts/`, `editorial/`, `tickets/` migrated into the workflow model as primitive-aware steps or plugins
- `auto.py` driver becomes a generic graph runner with zero phase-name knowledge — drives any workflow YAML
- All profile TOMLs migrated to pipeline configurations OR retained with auto-derived workflow mapping
- Every existing `megaplan` CLI subcommand continues to pass its golden test on the new engine
- `chain.py` deleted; legacy fallback removed; `MEGAPLAN_LEGACY_CHAIN` no longer recognised
- Cloud preflight + redact pipelines re-validated against new artifact emission shapes

**`megaplan plan` idea:**
> Migrate the execute phase, receipts pipeline, editorial doc-assembly, and ticket lifecycle into the new primitive model as composable steps. Convert the auto-driver into a generic workflow-graph runner with zero hardcoded phase names. Convert all profile TOMLs into workflow configurations (or keep them as role-mapping shortcuts that resolve to a workflow). Retire `chain.py` entirely. Every existing `megaplan` CLI subcommand must continue to pass its golden test on the new engine; resident daemon and cloud runners must keep working.

### Sprint 5 — Hardening, Docs, Cutover (2 weeks)
**DoD:**
- Live `megaplan` repointed at refactored code (symlink swap + venv promotion)
- `megaplan-next` retired; one entrypoint
- Full test matrix green in CI (where available, otherwise locally scripted):
  - planning end-to-end on all-Claude / all-Codex / standard / nancy / marlowe profiles
  - multi-critique doc end-to-end
  - one trivial third workflow ("joke mode") shipped as smoke test of composability
- `docs/authoring-a-workflow.md` written
- Resident daemon runs ≥24h on next-binary in a side venv with Discord muted before promotion
- Promotion checklist (from backcompat critique) executed and signed off

**`megaplan plan` idea:**
> Cut the live `megaplan` CLI over to the refactored primitive engine, retire the parallel `megaplan-next` entrypoint, and ship a primitive-authoring guide plus a trivial third workflow (joke mode: `LLMCall(comedian) → Critique(groucho) → Revise → Materialize`) as a composability smoke test. Run the full test matrix (planning end-to-end across 5 profiles + multi-critique end-to-end + joke-mode smoke). Resident daemon must run 24h on the next-binary in a side venv before symlink swap. Promotion checklist (artifact byte-compat, CLI help diff, 5 historical plans replay, chain spec replay on non-Veas repo) must be signed off.

## Live status

- [x] Worktree created
- [x] Source briefing read
- [x] 3 critique subagents spawned and returned
- [x] Plan revised from critiques
- [x] Sprint breakdown drafted (Sprint 0 + 5)
- [ ] Sprint 0 — Isolation & Baseline (in progress)
- [ ] Sprint 1 — Loop Taxonomy + Primitive Spec
- [ ] Sprint 2 — Multi-Critique MVP (falsification sprint)
- [ ] Sprint 3 — Refactor planning phases
- [ ] Sprint 4 — Refactor execute/receipts/editorial/tickets
- [ ] Sprint 5 — Hardening + cutover
- [ ] End-to-end validation pass

Updated after each sprint chunk completes. Principles restated above at every update.
