# Sprint B — Planning parity + cutover

> **Superseded by [sprint-b-revised.md](sprint-b-revised.md).** The YAML
> runtime experiment was killed in megaplan 0.22.0. Python composition
> (`Pipeline.builder()`, `patterns.py`) is the framework. The 5
> architectural decisions that blocked the original Sprint B run ($747,
> iter 33, state=blocked) are resolved in the revised brief. Do NOT
> execute this brief — read `sprint-b-revised.md` instead.

## Goal

Move today's `planning` pipeline onto the YAML runtime that Sprint A built. Parity-gate the YAML path against `planning.py` on a curated real-model corpus, flip the default, delete `planning.py` + `parallel_critique.py`, and migrate the `megaplan-decision` skill into `pipelines/planning/`. **This is the high-stakes sprint** — a regression here breaks the core megaplan loop.

## Prerequisite

Sprint A must be merged. Specifically:

- `pipelines/planning/pipeline.yaml` exists and loads (parked by Sprint A).
- All 4 step kinds (`agent`, `panel`, `gate`, `human_gate`) work for `writing-panel-strict`.
- Pipeline-local profile resolution + `extends =` work.
- Sprint A's prep phase produced the **handler audit** (a per-`handle_*`-function breakdown of non-prompt LOC and side-work). That document is the primary input here.

## Authoritative spec

- `docs/yaml-pipelines-migration.md` — design doc.
- `.megaplan/briefs/yaml-pipelines-sprint-a.md` — Sprint A brief (for schema reference + the handler audit it produces).
- Ticket `01KRVVDSGPFJQEJ2JBB81CYPTQ`.

## Decisions already locked (do not re-debate)

### Parity rubric — what "passes" means

Semantic parity, not byte parity. The YAML path passes when, on every corpus input, all of the following hold versus the Python path:

1. **Same stage transition graph.** Identical sequence of stage entries/exits. Identical edge selections at gates.
2. **Same gate `recommendation` values.** If Python gate returned `proceed`, YAML gate returns `proceed`. Per-flag IDs raised may differ in text but must overlap by ≥80% on stable flag-ID set (defined below).
3. **Stable flag-ID set** (the flags whose presence/absence is parity-load-bearing): `architecture_drift`, `scope_expansion`, `untested_assumption`, `concurrency_hazard`, `migration_unsafe`, `cost_overrun`, `escalate_required`, `tiebreaker_required`. Any flag in this set raised by Python must also be raised by YAML (and vice versa) on ≥7 of every 10 runs.
4. **Same iterate-loop count ±1.** If Python iterates 3 times, YAML iterates 2-4. Documented as drift if equal to ±1.
5. **Cost-and-token totals within ±15%** at the run level (not per-phase). Larger drift = investigate.
6. **No new external-side-effects.** Same files touched, same artifact paths produced, same telemetry events emitted.

**What is explicitly NOT parity:** prompt assembly text, model outputs verbatim, retry counts, latency, exact phase ordering when ordering is unspecified.

### Parity corpus

Five inputs minimum, each chosen to trigger a specific edge case. Each input is committed under `pipelines/planning/tests/parity/<name>/` with `brief.md` + an `expected.yaml` capturing the parity-load-bearing stable-flag set and iterate-count band.

| Input | What it triggers |
|---|---|
| `01-trivial-doc-fix.md` | Smallest happy path: plan → execute → review, no critique escalation. Mode `doc`. Should iterate 0-1 times. |
| `02-cross-cutting-refactor.md` | Triggers `architecture_drift` flag + iterate loop. Mode `code`. Iterates 2-4 times. |
| `03-tiebreaker.md` | Forces tiebreaker subpipeline (critique splits 1-1, gate must arbitrate). Mode `code`. |
| `04-escalate.md` | Forces `escalate_required` flag (scope blown, model asks for human review). Mode `code`. |
| `05-joke-with-revise.md` | Joke mode + at least one revise pass. Validates mode-suffix prompt resolution + PromptRegistry path. |
| `06-creative-essay.md` *(optional 6th)* | Creative mode without form_id concerns. Validates mode passthrough where form selection happens inside the prompt. |

Building this corpus is real work — budget 2 days. The inputs come from real plans Peter has already run; mine `.megaplan/plans/` for candidates rather than inventing them.

### State-file backward-compat

7. **In-flight plans use the path they started on.** A plan started under `planning.py` finishes under `planning.py`; a plan started under YAML finishes under YAML. State files record `pipeline_runtime: legacy | yaml` at init; resume honors it.
8. **Drain period ≥ 14 days** before deleting `planning.py`. Cutover = flip default. Deletion = separate commit after drain confirms no `pipeline_runtime: legacy` resumes remain.
9. **No state migration tool.** If 14 days isn't enough for a given user's in-flight plans, they finish under the legacy path or restart.

### Mode-overlay extraction

10. **`mode_overlay` lives in `_pipeline/executor.py`**, not in pipeline-specific code. The executor reads `supported_modes:` from `pipeline.yaml`; rejects unsupported modes at run start; passes mode through to PromptRegistry's existing `<key>:<mode>` suffix mechanism unchanged.
11. **`metaplan` mode** — out of scope. Stays as-is in the registry; planning's YAML declares it in `supported_modes:` for parity but no new wiring.

### Handler escape-hatch budget

12. Sprint A's handler audit produces a list. **Maximum 3 stages in `pipelines/planning/pipeline.yaml` may use `handler: <python_callable>`.** Each one gets a tracked ticket for how it generalizes by a future sprint. Anything beyond 3 = the YAML is decorative, escalate to redesign.
13. Likely-but-not-certain escape-hatch candidates (audit confirms): tiebreaker subpipeline integration, feedback-loop wiring, finalize's artifact-batching logic. If audit says <3 of these need handlers, even better.

### Cutover ceremony

14. **Two PRs, not one.** PR1: parity gate green, both paths exist, default is still `legacy`, `--use-yaml-pipeline` flag opt-in. PR2: flip default to `yaml`, add `--use-legacy-pipeline` escape, do NOT delete `planning.py` yet.
15. **Deletion PR is a third PR** after the 14-day drain. Removes `planning.py`, `parallel_critique.py`, the legacy escape flag, and the runtime-selector branch in the executor.

### Skill migration

16. **`megaplan-decision` keeps its name and location** (`~/.claude/skills/megaplan-decision/SKILL.md`). It gets a frontmatter tweak making explicit that it's the planning-pipeline rubric.
17. **`pipelines/planning/SKILL.md` is a symlink** to the same file. Users who install the planning pipeline get the rubric automatically.

## Scope (≤2 weeks)

### In
- Build the parity gate (`tests/parity/run_parity.py` or `megaplan parity-test <pipeline>`): runs both paths on each corpus input, compares against the rubric, emits a report.
- Author the parity corpus (5-6 inputs, briefs + `expected.yaml`).
- Author `pipelines/planning/pipeline.yaml` (referencing existing PromptRegistry keys — NO prompt migration).
- Wire critique stage as `kind: panel, produces: verdict, merge: structural`. Absorb `parallel_critique.py`'s aggregation into `PanelStep` (per Sprint A's `merge: structural` knob already designed).
- Add `default =` to every TOML profile that doesn't already have it (Sprint A should have done this; verify).
- Executor: handle both runtime paths cleanly; mode_overlay extraction.
- CLI: `--use-yaml-pipeline` / `--use-legacy-pipeline` flags; `megaplan plan` keeps working through both.
- Three PRs as specified above. PR2 flips the default.
- `pipelines/planning/SKILL.md` symlink + `megaplan-decision` frontmatter tweak.
- Update `docs/pipeline-architecture.md` if it asserts anything legacy-pipeline-specific.

### Out (explicit anti-scope)
- **Do NOT migrate prompts** from Python to markdown. Ticket rule #1.
- **Do NOT touch `creative` mode form handling.** Locked.
- **Do NOT add new step kinds.** If parity needs one, that's a design gap — escalate.
- **Do NOT auto-register skills into `~/.claude/skills/`.** Separate piece.
- **Do NOT add per-stage retry/error policy, budget caps, or `produces:` typing.** Sprint 4+.
- **Do NOT clean up `prompts/*_joke.py` shims** into .md files. Cosmetic, defer.
- **Do NOT modify `subloop.py` beyond what's needed to invoke it from YAML.**
- **Do NOT touch `megaplan cloud`** unless the audit shows cloud invokes `planning.py` server-side (in which case stop and escalate — that's a separate decision).

## Done criteria

1. Parity gate runs all corpus inputs in CI on every PR touching `_pipeline/` or `pipelines/planning/`. Green = all rubric criteria met on all inputs over 3 consecutive runs.
2. One real-model parity pass (not mocked) on the full corpus, results reviewed manually. Cost report inside ±15% per the rubric.
3. PR1 merged: both paths exist, `--use-yaml-pipeline` opt-in works, default still legacy.
4. PR2 merged: default is YAML, `--use-legacy-pipeline` escape works, parity gate stays green.
5. After 14 days: PR3 merged, `planning.py` + `parallel_critique.py` deleted, legacy flag removed.
6. `~/.claude/skills/megaplan-decision/` frontmatter updated; `pipelines/planning/SKILL.md` symlink in place; `megaplan describe planning` renders it.
7. No in-flight plan broke during cutover. Spot-check via state-file audit.

## Touchpoints

- New: `tests/parity/`, parity-corpus inputs under `pipelines/planning/tests/parity/`
- New: `pipelines/planning/pipeline.yaml`, `pipelines/planning/SKILL.md` (symlink)
- Changed: `megaplan/_pipeline/executor.py`, `megaplan/_pipeline/steps/panel.py` (absorb parallel_critique aggregation), `megaplan/cli.py`
- Deleted (in PR3): `megaplan/_pipeline/planning.py`, `megaplan/orchestration/parallel_critique.py`
- Touched: `~/.claude/skills/megaplan-decision/SKILL.md` (frontmatter only)
- Maybe touched (audit decides): `megaplan/_pipeline/subloop.py` for tiebreaker integration

## Open questions the parity gate will surface (not pre-answerable)

These are the unknown-unknowns. Honest: the parity gate's value comes from *finding* these, not pre-listing them.

1. Which `handle_*` functions actually need `handler:` escape-hatches once audit + parity reveal the seams.
2. Whether tiebreaker invocation crosses the YAML/legacy boundary cleanly or needs special-casing.
3. Whether iterate-loop counts drift more than ±1 in practice (rubric says ±1; reality may force a wider band).
4. Whether the stable-flag-ID set above is correct or needs adjustment after seeing real divergences.
5. Whether `megaplan cloud` calls `planning.py` server-side (audit early; if yes, this brief reduces to "prerequisite for a cloud-coordinated sprint").

**If any of these surface as redesign-worthy (not just spec-tweak-worthy), stop and escalate before forcing parity green.** A parity gate gamed to pass is worse than no parity gate.

## Profile recommendation for this sprint

`apex/thorough/high` — Tier 5. Cutover where regression = the core megaplan loop breaks. Apex's two-vendor split earns its keep: Codex's structural-analysis bias catches parity-rubric edge cases (schema-shape drift, flag-ID divergence); Claude's repo-reading bias holds the migration code together. `--vendor` is silently ignored at apex — it's vendor-locked by design.

- *Robustness `thorough`* — 8 critique checks + parallel critique.
- *Depth `high`* — parity-gate code has real edge cases; planner needs deliberation.
- *Prep included free at `thorough`* — no `+prep` flag needed.

CLI: `megaplan init <this-brief> --profile apex --robustness thorough --depth high --project-dir ~/Documents/.megaplan-worktrees/yaml-pipelines-migration --work-dir ~/Documents/.megaplan-worktrees/yaml-pipelines-migration`

Run inside a subagent. This sprint continues in the same worktree Sprint A created — see below.

## Worktree isolation

This sprint runs in the **same worktree as Sprint A**: `~/Documents/.megaplan-worktrees/yaml-pipelines-migration/` on the `yaml-pipelines-migration` branch. No new setup needed if Sprint A has merged into that branch.

**Verify before kicking off:**

```bash
cd ~/Documents/.megaplan-worktrees/yaml-pipelines-migration
git status                                   # clean
git log --oneline -5                         # Sprint A commits present
ls megaplan/_pipeline/steps/                 # agent.py, panel.py, human_gate.py exist
ls pipelines/writing-panel-strict/           # Sprint A's pipeline shipped
ls pipelines/planning/pipeline.yaml          # Sprint A parked this
cat docs/yaml-pipelines-migration.md | grep -A1 "handler audit"   # Sprint A's audit appendix landed
```

If any of those fail, Sprint A isn't done — don't start Sprint B.

**Merge ceremony to `main`**:

- PR1 (parity gate green, both paths exist, default still legacy): merges `yaml-pipelines-migration` → `main` from the worktree.
- PR2 (flip default to YAML): branch off `main` again, do the flip, PR back.
- PR3 (deletion after 14-day drain): same pattern.

After PR3 merges, the worktree can be removed (`git worktree remove ~/Documents/.megaplan-worktrees/yaml-pipelines-migration`).

**Other tools using megaplan** (vibecomfy, reigh, lota, etc.) continue against `main` throughout — they only see the changes after each PR merges. Sprint A's PR1 introduces the YAML runtime but keeps planning on the Python path, so downstream tools experience no behavior change until PR2 flips the default. Coordinate the PR2 timing with anything actively running long-iterate plans.
