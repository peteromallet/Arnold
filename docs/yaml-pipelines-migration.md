# YAML pipelines + per-pipeline skills — migration design

> **Archived historical record — Python composition replaced YAML. See [docs/pipelines.md](pipelines.md).**
>
> This document is retained as the archived historical record of the YAML-pipelines experiment (Sprints A/B). The YAML runtime was removed in megaplan 0.22.0; pipelines are now defined as Python modules using `Pipeline.builder(...)` and the pattern library at `megaplan/_pipeline/patterns.py`. Do not treat the design notes below as current API guidance; read `docs/pipelines.md` for the current framework.

Companion to ticket `01KRVVDSGPFJQEJ2JBB81CYPTQ` (generic YAML pipelines framework). That ticket establishes **what** the runtime becomes; this doc extends it with **per-pipeline skill docs** and **pipeline-local profiles**, and lays out the work to migrate today's `planning` + mode variants + parallel critique onto the new shape.

The headline shift: a pipeline becomes a **self-contained folder** — topology, prompts, models, and "how to drive me" knowledge all colocated. Drop it in `~/.megaplan/pipelines/foo/` and it shows up as a runnable sequence *and* a skill Claude knows when to invoke. Same way a ComfyUI custom node ships its definition, presets, and docs together.

---

## End-state anatomy

```
pipelines/<name>/
  pipeline.yaml            # topology: stages, edges, prompt refs, slot names
  prompts/*.md             # prompt bodies (optional — can reference PromptRegistry keys)
  profiles/*.toml          # pipeline-local profiles (optional)
  SKILL.md                 # how to drive this pipeline (optional — minimum is description: in pipeline.yaml)
```

Discovery: `megaplan/pipelines/` (builtin) + `~/.megaplan/pipelines/` (user). Flat namespace until collisions force qualification.

### The simplicity ↔ complexity gradient

Every optional file represents a rung. Authors choose how far up to climb:

| Rung | Files needed | What the author gets |
|---|---|---|
| 0 — bare | `pipeline.yaml` only (with inline prompts, no profiles, no skill) | Runnable with system profiles + defaults. ~50 LOC YAML. |
| 1 — split prompts | + `prompts/*.md` | Long prompts move out of YAML. |
| 2 — custom models | + `profiles/*.toml` | Pipeline ships its own model recipes (e.g. "panel-of-7 wants Kimi for every reviewer"). |
| 3 — rich skill | + full `SKILL.md` (rubric-style) | Claude/Codex consults the skill to pick which profile/mode for the work. |

Every rung is opt-in. Rung 0 is real and supported; rung 3 looks like the megaplan-decision experience but scoped to one pipeline.

---

## Profile resolution order

Sequence declares slot names; profile fills them. The resolver walks four layers in order, fails loud on miss:

1. **CLI flag** — `--profile detectives:holmes-claude` (system-namespace) or `--profile @writing-panel-strict:premium` (pipeline-local namespace, leading `@`).
2. **Pipeline-local profile** — `pipelines/<name>/profiles/*.toml`. Scoped to this pipeline only. Can either define net-new slots (e.g. `reviewer_pessimist`) or override system ones.
3. **System profile** — `megaplan/profiles/*.toml` (unchanged from today).
4. **Profile `default`** — every profile gets a new `default = "..."` line (ticket already covers this). Catches unmapped slots.

Pipeline YAML declares both `default_profile:` and `recommended_profiles:` (the latter feeds the skill / `megaplan list pipelines --verbose`). If neither pipeline-local nor system profile resolves a stage's slot, fail at load time, not at runtime.

---

## SKILL.md — two flavors

**Minimum viable** — the `description:` field in `pipeline.yaml` is enough. `megaplan list pipelines` shows it; Claude can read it to decide when to call. No separate file.

**Full skill** — `SKILL.md` with frontmatter, modeled on `megaplan-decision`:

```markdown
---
name: pipeline-writing-panel-strict
description: Use for prose drafts (essays, posts, long-form replies) that need adversarial review from N reviewers before revision. Not for code, not for fact-heavy content.
---

# When to use this pipeline
[trigger criteria, exclusions]

# Dials you control
- `--reviewers=N` — how many panelists (3-9)
- `--profile @<this>:premium|standard|cheap`
- `--mode polish | restructure | provoke`

# How to pick a profile
[mini-rubric: stakes / budget / desired criticism style → profile]

# Examples
[1-2 sample invocations with rationale]
```

These can be auto-registered as Claude Code skills at install time (Sprint 4 candidate) — but even before that, `megaplan` can read them and surface guidance via `megaplan describe <pipeline>`.

---

## Migration of existing flows

Today's Python is doing four jobs we have to peel apart and re-express as YAML:

### 1. `planning` (the core flow) → `pipelines/planning/`

- `pipeline.yaml` with stages: `prep → plan → critique(panel) → revise → gate → execute → finalize → review → loop?`
- Critique becomes `kind: panel, produces: verdict, merge: structural` (3 reviewers — the current parallel_critique fanout)
- Prompts reference existing PromptRegistry keys for Sprint 2 — **do not migrate to .md yet** (ticket rule #1)
- `default_profile: detectives:holmes-claude` (or whatever current default is)
- `recommended_profiles:` enumerates the existing tier ladder
- `SKILL.md` is **the existing `megaplan-decision`**, repointed to live under this pipeline. It keeps the name `megaplan-decision` — the rubric is the planning-pipeline rubric, and that's accurate. Other pipelines will ship their own differently-named skills (e.g. `writing-panel-rubric`); there is no global "rubric router" skill in v1.

### 2. `code` / `doc` / `joke` / `creative` modes → stay as `--mode` runtime parameter

These are **not separate pipelines**. They're prompt overlays resolved via PromptRegistry's existing `<key>:<mode>` suffix mechanism. YAML keeps mode as a passthrough; `pipeline.yaml` declares `supported_modes: [code, doc, joke, creative]`.

Two specifics:
- **`creative + form_id`** — `form_id` is **not** modeled as a YAML axis. It was a bad abstraction — it only applies to creative writing and doesn't generalize. Instead, form selection lives **inside the prompt itself** (the creative pipeline's prompt asks the model to pick / honor a form) and any guidance for *which* form to pick lives in the creative pipeline's `SKILL.md`. The runtime sees one axis (mode); the form concern stays where it belongs (prompts + skill).
- **`joke` Python shims** (`prompts/*_joke.py`) — leave alone in Sprint 2. Convert to `.joke.md` later as cosmetic cleanup. Not on the critical path.

### 3. `parallel_critique.py` → absorbed into `PanelStep`

`orchestration/parallel_critique.py` becomes the implementation of `kind: panel` in `_pipeline/steps/panel.py`. File deleted at end of Sprint 3. No behavioral change — the planning pipeline's critique stage uses it via YAML reference and gets the same fanout, same Verdict aggregation.

### 4. `metaplan` mode → eventual `pipelines/metaplan/`

Currently underwired. Becomes its own pipeline when someone needs it. Not Sprint 1-3.

---

## Skill-doc migration for `megaplan-decision`

The existing `megaplan-decision` skill (~463 lines) is **planning-specific** even though it doesn't say so. Concretely:

1. The skill keeps its name (`megaplan-decision`) and stays where Claude Code finds it (`~/.claude/skills/megaplan-decision/SKILL.md`). It just gets a frontmatter tweak to make explicit that it's the rubric for the **planning** pipeline.
2. The pipeline directory `pipelines/planning/SKILL.md` is a symlink or generated copy pointing at the same content — so the skill ships *with* the pipeline (a user installing the pipeline gets the rubric automatically) but Claude Code keeps reading it from the skills dir.
3. Each new pipeline shipped in Sprint 3 (writing-panel-strict, code-review-panel) gets its own differently-named skill (e.g. `writing-panel-rubric`, `code-review-rubric`) following the same pattern.

There is **no global rubric-router skill** in v1 — `megaplan-decision` remains the planning rubric, full stop. If a future "overall report" skill or top-level entry point is wanted, that's a separate piece of work outside this migration.

---

## Work breakdown — what to build (delta over the existing ticket)

The ticket already covers schema/loader/executor/steps/resume. This doc adds:

### Pipeline-local profiles
- **`megaplan/profiles/__init__.py`** — extend resolver to look in `pipelines/<name>/profiles/` before falling back to system profiles. Namespace pipeline-local profile names with `@<pipeline>:` prefix to disambiguate.
- **`pipeline.yaml`** schema additions: `default_profile:`, `recommended_profiles: [...]`.
- **CLI** — accept `--profile @<pipeline>:<name>` syntax; `megaplan list profiles` groups by source (system vs pipeline-local).

### Skill docs
- **`pipeline.yaml`** schema additions: `description:` (required, one-liner), `when_to_use:` (optional, longer form), `dials:` (optional, structured map of CLI flags this pipeline exposes).
- **`megaplan describe <pipeline>`** new command — prints `pipeline.yaml` metadata + renders `SKILL.md` if present.
- **`megaplan list pipelines --verbose`** — shows each pipeline's `description:` + presence of `SKILL.md`.
- **Skill auto-registration** (Sprint 4) — install-time hook that symlinks `pipelines/*/SKILL.md` into `~/.claude/skills/megaplan-pipeline-<name>/` so they show up as first-class Claude Code skills. Optional; pipelines work fine without it.

### Mode handling on YAML path
- **`_pipeline/executor.py`** — historical mode-dispatch handling moves out of `planning.py` (which this abandoned migration expected to delete) into the executor itself. Reads `supported_modes:` from pipeline.yaml; passes mode through to PromptRegistry resolution unchanged.

### Sprint placement

The base ticket scopes this as 3 sprints + an optional Sprint 4. **That may be overkill for the actual work.** Peter's call: the mock-harness/parity-gate machinery exists to de-risk a multi-week migration; if the whole thing can land in one sprint with a real-model parity pass at the end, the staged-flag dance disappears. Default to compressed unless something during Sprint 1 forces a split.

**Compressed (one sprint, target):**
- Land schema + loader + Agent/Panel/HumanGate steps + executor changes + planning YAML + writing-panel YAML in one push.
- Parity-gate planning against the existing Python path via a real-model run on a curated input set (not a long-lived mock harness).
- Delete `planning.py` and `parallel_critique.py` in the same PR once parity passes.
- Ship `megaplan describe`, pipeline-local profile resolution, and the first `SKILL.md` (planning's = `megaplan-decision`) together.

**Fallback split (only if Sprint 1 surfaces real problems):**
- Sprint 1 = primitives + writing-panel, planning untouched.
- Sprint 2 = planning parity + cutover.
- Skill auto-registration into `~/.claude/skills/` always trails as a separate small piece — no need to bundle.

What ships regardless: `description:` + `default_profile:` in the YAML schema, pipeline-local profile resolution, the planning SKILL.md (existing `megaplan-decision` content), and at least one new pipeline (`writing-panel-strict`) to prove the abstraction outside planning's shape.

---

## Locked decisions

Recorded so the migration doesn't relitigate them mid-flight.

1. **Form-id is not a YAML concept.** Folded into the creative pipeline's prompt + documented in its `SKILL.md`. It was a bad abstraction — it only applies to creative writing.
2. **Rubric stays named `megaplan-decision`.** It's the planning pipeline's rubric and we're keeping the name. No global rubric-router skill in v1. (If a broader "overall report" skill emerges later, that's separate work and won't displace this one.)
3. **Pipeline input schema** — keep what works today. `megaplan run <pipeline> <input-path>` takes a file path; the pipeline knows what to do with it. No new schema layer required.
4. **Pipeline versioning** — fine to have, low priority. State file should snapshot the pipeline name + a content hash at run start so an in-flight resume after a YAML edit doesn't silently change topology. Don't build version-range matching or migration tooling.
5. **Skill-name collisions on auto-registration** — overwrite. If a pipeline ships a skill that collides with an existing one in `~/.claude/skills/`, the pipeline wins. Document the behavior; don't try to merge or namespace defensively.
6. **Credentials / missing model access** — **fail loudly, don't fall back silently.** If a pipeline's `default_profile` references a model the user has no credentials for, abort load and present the user with options: (a) provide a key, (b) sign in, (c) re-run with a different `--profile`. No automatic substitution. Claude is the platform default for "what would I run if you said nothing," but that's a CLI/config-level decision, not an in-pipeline fallback.
7. **Pipeline-local profile inheritance** — yes. `pipelines/foo/profiles/premium.toml` can declare `extends = "system:detectives:holmes-claude"` and override individual slots. Without this, pipeline-local profiles duplicate the 12-slot block constantly.
8. **Cost telemetry** — pipeline name flows through to the existing telemetry record so `megaplan history` can group by pipeline. No new dashboard work in this migration.
9. **Mock harness / parity gate** — not a permanent fixture. A real-model parity run on a curated input set at cutover is the gate, not a CI-resident mock matrix. Keeps scope honest with the compressed-sprint plan above.
10. **Test inputs / parity corpus location** — colocated with the pipeline (`pipelines/<name>/tests/`). Makes user-installed pipelines self-contained.

## Open questions worth a second pass

These aren't blockers, but flag them in the first PR's description so reviewers weigh in:

1. **Skill auto-registration mechanism.** Symlink vs. generated file vs. manifest the harness reads. Doesn't affect SKILL.md format, so deferrable — but the choice affects how cleanly user-installed pipelines drop in.
2. **Pipeline naming when a user pipeline shadows a builtin.** Today: flat namespace. The base ticket already says we'll qualify (`builtin/foo` vs `user/foo`) only when a real collision appears. Re-check this once the first user-supplied pipeline shows up.

---

## What this preserves vs changes

**Preserved:**
- Profile system (TOML, slot-based, system-level profiles in `megaplan/profiles/`)
- Rubric-style decision documents for nontrivial pipelines
- Mode parameter (`code`/`doc`/`joke`/`creative`) and its PromptRegistry suffix mechanism
- All existing prompts (Python files, not migrated)

**Changed:**
- One pipeline becomes many, defined in YAML
- Profiles can live with their pipeline (not just system-wide)
- `megaplan-decision` is explicitly the planning pipeline's rubric (name unchanged); other pipelines ship their own differently-named rubrics
- Failure on missing credentials becomes explicit and user-facing instead of any silent fallback

**Net new:**
- `SKILL.md` per pipeline (optional, gradient from one-line description to full rubric)
- Per-pipeline directories discoverable from `~/.megaplan/pipelines/`
- Pipeline content-hash recorded in state file (cheap versioning)
- Skill auto-registration path (post-migration, separate piece)

The whole point: simple cases stay one YAML file, complex cases get the same rubric experience we already use for planning — but scoped, plural, and user-extensible.

---

## Appendix: planning.py handler audit (Sprint A prep output)

### Scope

This audit covers all `handle_*` functions in `megaplan/handlers/` that participate in the planning pipeline (`planning.py`). The goal is to quantify how much non-prompt logic each handler carries so Sprint B's YAML migration can correctly size the `handler:` escape-hatch — if most handlers are thin wrappers around a model call, YAML can express them declaratively; if some carry heavy side-work, they need an escape hatch.

### Confirmation: `planning.py` has zero `handle_*` functions

`megaplan/_pipeline/planning.py` (300 lines) defines **zero** `handle_*` functions. It is purely a compile target: it builds a `Pipeline` dataclass graph of `Stage` objects (`prep → plan → critique → gate → finalize → execute → review → tiebreaker`). Each `Stage` delegates to an in-process `Step` class under `megaplan/_pipeline/stages/`, which in turn wraps the corresponding `handle_*` in `megaplan/handlers/`. The wrapping chain is:

```
planning.py (compile) → stages/<phase>.py (Step.run) → InProcessHandlerStep → handlers/<phase>.py (handle_*)
```

The historical placeholder Step (line 43–62 in the old audit) raises `NotImplementedError` and is only used for `tiebreaker_pending`/`tiebreaker_ready` lookups for the YAML gate tiebreaker subloop — it is never invoked by the executor path.

### Per-handler audit

| Handler | File | Function LOC | % non-prompt | Side-work description | Escape-hatch needed? |
|---|---|---|---|---|---|
| `handle_prep` | `handlers/plan.py:80-103` | 24 | ~96% | State validation (`require_state`), artifact write (`prep.json`), joke-mode primary-criterion extraction from worker payload, state advancement to `STATE_PREPPED` | **No** — nearly pure model-call wrapper; the joke-mode extraction is a small special case. |
| `handle_plan` | `handlers/plan.py:19-78` | 60 | ~87% | State validation (validates `initialized`/`prepped`/`planned`), joke-mode guard (primary_criterion required), rerun detection, success-criteria merge (`_merge_imported_decision_criteria`), plan-version write (`_write_plan_version` with meta), state advancement to `STATE_PLANNED`, iteration tracking, `last_gate` reset | **No** — well-structured bookkeeping; all steps share this pattern. |
| `handle_critique` | `handlers/critique.py:49-190` | 142 | ~80% | State validation, profile expansion, robustness-gate (bare rejects), active-check selection (`select_active_checks`), parallel-vs-sequential dispatch (`run_parallel_critique` for hermes, `_run_worker` for others), fallback on parallel failure, check validation (`validate_critique_checks`), recovery from `critique_output.json`, verifiability flag injection, creative-mode directors-notes update, flag-registry update (`update_flags_after_critique`), recurring-critique computation, scope-creep detection, `gate.json` stub for light robustness, state advancement to `STATE_CRITIQUED` | **Yes** — the robustness gating (bare skips entirely), parallel-fallback logic, scope-creep detection, and light-robustness gate-stub injection are all planning-specific control flow that a generic YAML executor won't replicate without a `handler:` escape hatch or a special `gate` step kind. The core critique (model call + flag collection) maps cleanly to `kind: panel` in YAML, but the surrounding orchestration is tightly coupled to planning's state machine. |
| `handle_revise` | `handlers/critique.py:205-283` | 79 | ~90% | State validation, profile expansion, gate-transition resolution (`_resolve_revise_transition`), previous-plan text read, notes-consumed tracking, model call, payload validation, success-criteria merge, plan-version write, plan-delta computation, state advancement, last-gate reset, flag-update (`update_flags_after_revise`), next-step computation, remaining-significant-flags tracking | **No** — same bookkeeping pattern as `handle_plan`; the plan-delta computation is a small reusable helper. |
| `_validate_tiebreaker` | `handlers/critique.py:285-380` | 96 | ~94% | Tiebreaker config guard (`allow_tiebreaker`), budget exhaustion check, blocklist filtering, required-fields validation, mechanical-recurrence signal check (`compute_iteration_pressure`, `has_mechanical_recurrence`), reprompt-if-no-signal logic, state advancement to `STATE_TIEBREAKER_PENDING` | **Yes** — this is a specialized gate sub-dispatch with iteration-pressure heuristics and reprompt logic. It's called from `handle_gate` when the gate recommends TIEBREAKER and lives in `critique.py` solely because of the cross-import chain (`gate.py` imports from `critique.py`). Sprint B will need `handler:` or a `tiebreaker_config:` section in the YAML gate step. |
| `handle_gate` | `handlers/gate.py:274-412` | 139 | ~87% | State validation, profile expansion, gate-signals artifact build (`build_gate_signals`, `run_gate_checks`), model call, orchestrator-guidance build, gate-summary assembly (`build_gate_artifact`), outcome application (`_apply_gate_outcome` with PROCEED/ITERATE/ESCALATE/TIEBREAKER dispatch), tiebreaker validation (calls `_validate_tiebreaker`), unresolved-flags reprompt with retry, resolution-tradeoff merge, debt-registry recording on PROCEED, last-gate store, emitter notification for ESCALATE/TIEBREAKER | **Yes** — the multi-recommendation dispatch (PROCEED → finalize, ITERATE → revise, TIEBREAKER → tiebreaker subloop, ESCALATE → override) is the heart of planning's state machine. The YAML `kind: gate` step in Sprint A already handles structured Verdict → routed edges; the question for Sprint B is whether planning's gate complexity (signals build, reprompt loop, debt recording, emitter hooks) fits entirely within that primitive or needs additional `handler:` side-work. Current assessment: ~80% of the gate's non-prompt LOC could become declarative edge routing, but the signals build + reprompt loop + debt registry are planning-specific and need an escape hatch. |
| `handle_finalize` | `handlers/finalize.py:411-431` | 21 | ~95% | State validation (allows `gated` + bare/creative bypass), model call, payload validation (`_validate_finalize_payload` with comprehensive task/user_action/sense_check checks), artifact write (`_write_finalize_artifacts` which captures test baseline, injects verification tasks + user-action gate tasks, reconciles validation), state advancement to `STATE_FINALIZED`, next-step set to `execute` | **No** — thin wrapper. The heavy lifting is in `_write_finalize_artifacts` (L329-409, ~80 lines of artifact assembly), but that's pure data transformation, not control flow. YAML `kind: agent` + a `produces: finalize` tag with post-processing hook would cover it. |
| `handle_execute` | `handlers/execute.py:75-257` | 183 | ~86% | State validation (`finalized`/`blocked`/`failed`), profile expansion, sandbox-divergence warning, destructive-confirmation gate, auto-approve/user-approved gate, agent resolution, fresh-session enforcement on rework/blocked retry, active-step tracking, batch-vs-auto-loop dispatch, blocked-result recording to lifecycle, prose/doc-assembly path, robustness-based review-skip stub injection, verifiability human-deferred detection, state advancement, phase-result emission | **Yes** — this is the most complex handler. The auto-approve gate, fresh-session logic, batch-vs-auto-loop dispatch, blocked recording, and review-skip stubs are all planning's execution model. The YAML executor path in Sprint A uses a different dispatch (the generic `AgentStep` + `PanelStep` + `HumanGateStep`), so the question is whether the `execute` phase in planning's YAML can be a plain `kind: agent` or needs the full handler machinery. Current assessment: planning's execute phase is not a single model call — it's an orchestrator loop (`dispatch_execute_auto_loop` or `dispatch_execute_one_batch`) with its own batch management, deviation tracking, and lifecycle hooks. This will need `handler:` in Sprint B. |
| `handle_review` | `handlers/review.py:439-574` | 136 | ~57% | State validation, profile expansion, sandbox-divergence warning, robustness-gated pre-check flags, prompt-override resolution, parallel-hermes vs single-worker dispatch, extreme-robustness parallel-review path (`run_parallel_review`), review-verdict merge (`_merge_review_verdicts`), rework-item synthesis, receipt emission, state advancement, phase-result emission | **Yes** — the robustness-gated dispatch (light/full/thorough vs extreme), pre-check flag injection, parallel-review fanout, and receipt emission are all planning-specific. The actual review model call maps cleanly to YAML `kind: agent`, but the surrounding control flow needs a `handler:` escape hatch. |
| `_finalize_review_outcome` | `handlers/review.py:320-436` | 117 | ~98% | Verdict-merging into `finalize.json`, `final.md` re-render, outcome resolution (`_resolve_review_outcome` with blocked/needs_rework/done dispatch), rework-cycle cap, deferred-must human-verification detection, active-step clearing, session-update, history-append, receipt build+write, state save, response construction | **No** (helper) — this is post-model bookkeeping that always runs after either review path. It's not a handler itself; it's called by `handle_review`. |
| `handle_tiebreaker_run` | `handlers/tiebreaker.py:34-71` | 38 | ~97% | State validation, gate-data extraction (question, flag_ids, fuzzy_group_id), args construction, subprocess tiebreaker dispatch (`_run_tiebreaker`), workflow transition, response construction | **No** — thin wrapper around the tiebreaker subloop. The subloop itself (`prompts/tiebreaker_orchestrator.py::_run_tiebreaker`) is complex, but this handler is just a dispatch gate. |
| `handle_tiebreaker_decide` | `handlers/tiebreaker.py:73-153` | 81 | ~100% | State validation, action parsing (pick/escalate/replan), tiebreaker-file discovery (researcher/challenger JSONs), `TiebreakerDecision` assembly, decision persistence, audit recording, flag settlement (if picking), state routing (escalate→awaiting_human, replan→planned, pick→critique) | **Yes** — this is a pure state-machine handler with zero model calls. It reads human input, persists decisions, and routes state. Sprint B will need `handler:` or a dedicated `tiebreaker_decide` step kind. |
| `handle_override` | `handlers/override.py:374-380` | 7 | ~100% | Dispatch table lookup + delegate to action-specific handler (`_override_add_note`, `_override_abort`, `_override_force_proceed`, `_override_replan`, `_override_set_robustness`, `_override_set_profile`) | **Yes** — override is a planning-specific concept (human intervention in the state machine). Each override action has its own handler logic in `override.py` (L46-L372, ~327 lines of non-handler helpers). Sprint B: `kind: human_gate` with `choices:` can cover some override cases, but the full override system needs `handler:`. |
| `handle_verify_human` | `handlers/verifiability.py:10-91` | 82 | ~98% | State validation, criterion lookup (by index or name), verification persistence to `human_verifications.json`, deferred-must detection, state advancement to `STATE_DONE` when all verified | **No** — operates on `STATE_AWAITING_HUMAN`, which is a terminal state. Not part of the planning pipeline's active stages. |
| `handle_audit_verifiability` | `handlers/verifiability.py:93-125` | 33 | ~100% | State loading, criteria audit via `audit_criteria` + `validate_requires`, results assembly | **No** — diagnostic command, not a pipeline stage. |

### parallel_critique.py output ordering

`megaplan/orchestration/parallel_critique.py::run_parallel_critique` (L201-285):

1. **Input ordering preserved.** Checks are submitted to `ThreadPoolExecutor` in input list order (L233-245, `for index, check in enumerate(checks)`). Results are collected by `index` in a pre-sized list (L222: `results = [None] * len(checks)`). After all futures complete, results are iterated in index order (L260-266) and assembled into `ordered_checks`. **Final output order = input check order.**

2. **Disputed overrides verified.** At L268-269:
   ```python
   disputed_flag_ids = _merge_unique(disputed_groups)
   disputed_set = set(disputed_flag_ids)
   verified_flag_ids = [flag_id for flag_id in _merge_unique(verified_groups) if flag_id not in disputed_set]
   ```
   If a flag appears in **both** the disputed and verified sets (from different reviewers), it is excluded from `verified_flag_ids`. **Disputed wins over verified.**

3. **`_merge_unique`** (L35-43) merges lists of flag IDs preserving order of first appearance, deduplicating within and across lists. This means within verified or disputed sets, flags appear in the order their checks first reported them (i.e., input check order).

### No existing `awaiting_user.json` shape to reuse

Confirmed by full-text search across the entire repository: **zero references to `awaiting_user`** exist anywhere in the codebase. The only existing resume mechanism is:

- `megaplan/_pipeline/resume.py::ResumeCursor` (100 lines) — reads/writes `state.json::resume_cursor` with `{"phase": "<stage_name>", "retry_strategy": "..."}`. This is the legacy failure-recovery cursor, not a human-gate pause mechanism.

Sprint A's `HumanGateStep` creates `awaiting_user.json` de novo. The `handle_resume` flow in `cli.py` will check for `awaiting_user.json` first; if absent, fall through to `ResumeCursor.load()`.
