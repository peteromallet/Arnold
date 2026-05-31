# Sprint A — YAML pipelines runtime + writing-panel + skills/profiles ecosystem

## Goal

Make `pipeline.yaml` a first-class megaplan primitive: ship the runtime that interprets YAML pipelines, deliver `writing-panel-strict` as the first non-planning pipeline, and wire the surrounding ergonomics (per-pipeline SKILL.md, pipeline-local profiles, credential-failure UX). **Today's `planning` pipeline remains on the Python path — Sprint A introduces zero risk to it.** Sprint B does the parity cutover separately.

## Authoritative spec

Two docs already on disk are the spec — read both before planning:

1. **`docs/yaml-pipelines-migration.md`** — design doc with locked decisions, simplicity-gradient, profile resolution order, SKILL.md format, and migration plan.
2. **Ticket `01KRVVDSGPFJQEJ2JBB81CYPTQ`** at `.megaplan/tickets/01KRVVDSGPFJQEJ2JBB81CYPTQ-generic-yaml-defined-pipelines-sequences-framework.md` — primitive set, filesystem layout, components/changes inventory.

This brief locks decisions concretely, supplies literal `pipeline.yaml` examples, and bounds scope to Sprint A.

## Why now

Today megaplan has one pipeline (`planning`) hardcoded in Python. Peter wants ~50 user-defined pipelines (writing-panel, code-review-panel, judge-of-N, etc.). Sprint A proves the abstraction by shipping one fully new pipeline end-to-end without touching planning. If the abstraction breaks here, fix it before Sprint B's high-stakes parity cutover.

## Decisions already locked (do not re-debate)

### Primitives & schema

1. **Four step kinds, period.** `agent` (single model, M inputs → 1 output), `panel` (N models in parallel, each its own prompt), `gate` (structured Verdict → routed edges), `human_gate` (pause/persist/exit, resume reads artifacts fresh from disk). Subpipeline reuses existing `_pipeline/subloop.py` by name; not generalized this sprint.
2. **YAML, not TOML.** Multi-line prompts win.
3. **`pipeline.yaml` schema** uses these top-level fields, validated by pydantic:
   ```yaml
   name: writing-panel-strict
   version: 1
   description: "Adversarial review of prose drafts by N reviewers, then revise. Not for code."
   inputs:
     - name: draft
       kind: file
       required: true
   supported_modes: [polish, restructure, provoke]   # optional; empty = mode flag rejected
   default_profile: "@writing-panel-strict:standard"  # required
   recommended_profiles: ["@writing-panel-strict:premium", "@writing-panel-strict:standard", "@writing-panel-strict:cheap"]
   stages:
     - id: panel_review
       kind: panel
       reviewers:
         - {id: pessimist, prompt: prompts/pessimist.md}
         - {id: optimist,  prompt: prompts/optimist.md}
         - {id: structuralist, prompt: prompts/structuralist.md}
       inputs: [draft]
       produces: markdown
       merge: none           # synth picks it up; no structural merge
     - id: synth
       kind: agent
       prompt: prompts/synth.md
       inputs: [panel_review.*]
       produces: markdown
     - id: revise
       kind: agent
       prompt: prompts/revise.md
       inputs: [draft, synth]
       produces: markdown
     - id: human_decide
       kind: human_gate
       artifact: revise
       choices: [continue, stop]
   edges:
     - {from: human_decide, when: continue, to: panel_review}   # loop back, rereading revise from disk
     - {from: human_decide, when: stop, to: done}
   ```
4. **Step input refs** — `inputs: [stage_id]` resolves to that stage's output; `inputs: [stage_id.*]` resolves to all sub-outputs of a panel; **panel ordering = YAML reviewer-list order** (locks base-ticket open Q5).
5. **Prompt refs** — string ending in `.md` = file path relative to `pipelines/<name>/`; anything else = PromptRegistry key. Mode suffix `<key>:<mode>` continues to work for registry keys.
6. **PromptRegistry pipeline keying** — keys are scoped by `pipeline.yaml`'s `name:` field (not directory slug). Locks base-ticket open Q4.
7. **Discovery** — `megaplan/pipelines/<name>/` (builtin) + `~/.megaplan/pipelines/<name>/` (user). Flat namespace; collision = user wins with a warning. No `builtin/` vs `user/` qualification yet.

### Profiles

8. **Resolution order** — CLI flag → pipeline-local (`pipelines/<name>/profiles/*.toml`) → system (`megaplan/profiles/*.toml`) → profile `default` field → fail-loud. The `default = "..."` field is added to every profile this sprint.
9. **Pipeline-local namespace** — `@<pipeline>:<profile>` on the CLI (e.g. `--profile @writing-panel-strict:premium`).
10. **Inheritance** — pipeline-local profiles may declare `extends = "system:detectives:holmes-claude"` (or `"@<other-pipeline>:<profile>"`) and override individual slots. Required so per-pipeline profiles don't duplicate 12-slot blocks.
11. **Credential failure** — at run start, before any phase fires, validate every slot's agent spec resolves to a model the user has credentials for. **Fail loudly with a structured prompt:**
    ```
    Pipeline 'writing-panel-strict' (profile 'premium') needs credentials for:
      • codex (slot: critique) — no OPENAI_API_KEY found
    Options:
      [1] Provide a key now (paste, will not be persisted)
      [2] Sign in (opens auth flow)
      [3] Pick a different profile (run `megaplan list profiles --pipeline writing-panel-strict`)
      [4] Abort
    ```
    No silent fallback. Non-TTY runs (CI, automation) fail with exit code 7 and the same message to stderr.

### SKILL.md / metadata

12. **`description:` in pipeline.yaml is required** — surfaced by `megaplan list pipelines`.
13. **Optional `SKILL.md`** alongside pipeline.yaml. Plain markdown with frontmatter (`name:`, `description:`). No auto-registration into `~/.claude/skills/` this sprint — that's a separate small piece after Sprint B.
14. **`megaplan describe <pipeline>`** new CLI command: prints metadata + renders SKILL.md if present.

### Human-gate semantics

15. **State on pause** — write `<plan_dir>/awaiting_user.json` with: pipeline name, version, current stage id, the resume choice list, the artifact path the user is being asked to inspect. Plan process exits 0. Resume via `megaplan resume <plan-dir> --choice continue|stop`.
16. **Resume reads artifacts fresh** — when resuming, all referenced artifact paths are re-read from disk. User edits to `revise/v1.md` between pause and resume ARE picked up.

## Scope (≤2 weeks)

### In
- `_pipeline/schema.py` (pydantic models + validator)
- `_pipeline/loader.py` (filesystem discovery from builtin + user dirs)
- `_pipeline/steps/agent.py`, `_pipeline/steps/panel.py`, `_pipeline/steps/human_gate.py` (gate logic reuses existing executor patterns — no new file)
- `_pipeline/executor.py` changes: consume `Pipeline` object alongside today's `planning.py` path; handle `awaiting_user` yield; mode_overlay logic stays in executor regardless of caller
- `megaplan/profiles/__init__.py` resolver: 4-layer order; `extends =` support; `@<pipeline>:<profile>` parsing; `default =` field in TOML schema
- CLI: `megaplan run <pipeline> <input>` (alias: `megaplan plan` stays pointing at Python planning path for now); `megaplan list pipelines [--verbose]`; `megaplan describe <pipeline>`; `--profile @x:y` parsing; structured credential-failure prompt
- `pipelines/writing-panel-strict/pipeline.yaml` + 3 reviewer prompts + synth + revise prompts + 1 pipeline-local profile (`standard.toml`) extending `system:detectives:holmes-claude`
- Per-stage artifact convention: `<plan_dir>/<stage_id>/[<persona>/]v<n>.<ext>`
- Tests: schema validation, loader discovery, profile resolution (all 4 layers), human-gate pause/resume mechanics, writing-panel-strict end-to-end with mocked agents

### Out (explicit anti-scope)
- **Do not touch `_pipeline/planning.py`.** It keeps running as today. Sprint B retires it.
- **Do not migrate any prompts** — neither planning's Python prompts to .md, nor joke shims. Ticket rule #1.
- **Do not modify `parallel_critique.py`** — Sprint B absorbs it into PanelStep during the planning cutover.
- **Do not build skill auto-registration** into `~/.claude/skills/`. Post-Sprint-B item.
- **Do not add `produces:` artifact-contract validation** beyond a free-form tag. Sprint 4 territory.
- **Do not promote `creative` to its own pipeline** or change form_id handling. Already-locked decision: form belongs in prompts + SKILL.md, not YAML.
- **Do not add `megaplan new <name> --from <template>`** scaffolder. Defer.
- **Do not redesign profile TOML format** beyond adding `default =` and `extends =`.

## Done criteria

1. `megaplan run writing-panel-strict path/to/draft.md` runs end-to-end with mocked agents; pauses at human-gate; resumes via `--choice continue` for one loop and `--choice stop` to exit.
2. Same invocation with `--profile @writing-panel-strict:standard` and `--vendor codex` resolves correctly through the 4-layer resolver.
3. `megaplan run writing-panel-strict path/to/draft.md` with no OPENAI_API_KEY (when profile demands codex) prints the structured credential prompt and exits non-zero; non-TTY mode exits 7 to stderr.
4. `megaplan list pipelines` shows both `planning` and `writing-panel-strict`. `megaplan describe writing-panel-strict` renders the SKILL.md.
5. `pipelines/planning/pipeline.yaml` exists and **loads without error**, but is NOT yet the runtime path for `megaplan plan` (that's Sprint B). The file is committed so Sprint B starts from a known-loadable shape.
6. All existing planning tests still pass unchanged. No regression in the `planning.py` codepath.
7. One real-model end-to-end run of writing-panel-strict on a curated draft input, output reviewed manually.
8. **Handler audit committed** as an appendix to `docs/yaml-pipelines-migration.md` (e.g. `## Appendix: planning.py handler audit (Sprint A prep output)`). Per-`handle_*`-function row: name, % non-prompt LOC, what kind of side work, whether it'll need a `handler:` escape-hatch in Sprint B's YAML. This is Sprint B's primary input — failing to land it strands Sprint B.

## Touchpoints

- `megaplan/_pipeline/` (new: schema.py, loader.py, steps/)
- `megaplan/_pipeline/executor.py`
- `megaplan/_pipeline/prompts.py` (resolver gains .md-path branch)
- `megaplan/profiles/__init__.py` + every `.toml` file in `megaplan/profiles/` (add `default =`)
- `megaplan/cli.py`
- `megaplan/pipelines/writing-panel-strict/` (new)
- `megaplan/pipelines/planning/pipeline.yaml` (new, parked)
- Tests under `tests/_pipeline/` + `tests/profiles/`

## Open questions for the prep phase to resolve

These are the ones front-loading can't kill — they need code inspection, not architecture decisions:

1. **Audit `handle_*` functions in `planning.py`** — how much non-prompt logic do they each carry? Output: a per-handler line item (handler name, % non-prompt LOC, what kind of side work). Determines whether `handler:` escape-hatch becomes the rule or stays a tracked exception. **This audit's output is the input to Sprint B.**
2. **Today's `parallel_critique.py` aggregation semantics** — confirm Verdict merge rules (field-by-field union? majority? first-non-empty?) so PanelStep's `merge:` knob has honest defaults.
3. **State-file format for `awaiting_user.json`** — does anything in today's `resume.py` already read a similar shape? Reuse if so.

If prep surfaces a primitive design gap (e.g. writing-panel actually needs a fifth step kind), **stop and escalate before continuing** — that's the kind of discovery worth replanning around, not papering over with a `handler:` field.

## Profile recommendation for this sprint

`partnered//high +prep @codex` — Tier 3 (cross-cutting novel code, but most architecture locked by this brief), `full` robustness (home base; no production regression possible since planning is untouched), `high` depth (schema is load-bearing), prep enabled to do the handler audit, codex as the premium vendor.

CLI: `megaplan init <this-brief> --profile partnered --depth high --with-prep --vendor codex --project-dir <worktree-path> --work-dir <worktree-path>`

Run inside a subagent per operating principles. If prep surfaces a design gap, `override set-profile premium` before continuing.

## Worktree isolation

**This sprint runs in a dedicated git worktree** so the main `megaplan/` checkout stays untouched and other tools currently using megaplan (vibecomfy, reigh, lota, etc.) keep working against `main`.

**Setup (manual, one-time before kicking off):**

```bash
# From the megaplan repo root on main:
git worktree add ~/Documents/.megaplan-worktrees/yaml-pipelines-migration -b yaml-pipelines-migration
cd ~/Documents/.megaplan-worktrees/yaml-pipelines-migration

# Optional: copy local profile overrides if any exist
cp -n .megaplan/profiles.toml .megaplan/profiles.toml 2>/dev/null || true
```

**Pass the worktree path explicitly** on every `megaplan` invocation in the sprint via `--project-dir` and `--work-dir`. Megaplan's CWD-walk-up discovery will hit the parent `.megaplan/` directory otherwise (see `_resolve_project_root` in `cli.py:2361` — exact issue the bakeoff orchestrator already documents). The flags exist precisely for this case.

**Sprint B uses the same worktree** — both sprints land on the `yaml-pipelines-migration` branch, which gets merged to `main` after Sprint B's PR3 (the deletion PR, after the 14-day drain).

**On megaplan's worktree support:** megaplan already has the building blocks — `megaplan/bakeoff/worktree.py` exposes `create_worktree`, `worktree_root`, `ensure_main_worktree_clean`. The bakeoff orchestrator uses these to spawn parallel runs into `~/Documents/.megaplan-worktrees/<exp>/<profile>/`. There's no single top-level `megaplan init --worktree` flag wrapping this for one-off sprints; we use `git worktree add` + `--project-dir`/`--work-dir`. Adding a convenience flag (`megaplan init --in-worktree <name>`) is a small follow-up — call it post-Sprint-B if useful, not part of this sprint's scope.
