# YAML pipelines + per-pipeline skills — migration design

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
- **`_pipeline/executor.py`** — mode_overlay logic moves out of `planning.py` (which is being deleted) into the executor itself. Reads `supported_modes:` from pipeline.yaml; passes mode through to PromptRegistry resolution unchanged.

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
