# Decorator-Template Emitter Completion Plan

Goal: drive the decorator-shape regenerated templates to **zero positional widgets, zero leftover helper nodes, and no surprise `raw_call` fallbacks for installed custom-node packs**. Reached via three independent sweeps that can run in parallel.

## Where we are right now

The decorator emitter (branch `feat/ready-template-decorator`, plus widget gap-fill on `fix/widget-alias-resolution-decorator`) produces correct-shape templates. Regenerating the 9 runexx templates surfaces three categories of residual problem, each with a different root cause and a different home for the fix.

### Category A — `GetNode` / `SetNode` / `Reroute` falling through as `raw_call`

```python
getnode   = raw_call('GetNode',   '1871', _outputs=('FLOAT',), name='fps')
getnode_2 = raw_call('GetNode',   '1919', _outputs=('INT',),   name='frames_seconds')
reroute   = raw_call('Reroute',   '1932', _outputs=('',))
```

Per the agent skill: helper/UI nodes are supposed to be stripped during conversion and not survive roundtrip. The helper-resolver `_resolve_helper_nodes_for_emission()` in `vibecomfy/porting/emitter.py` walks the broadcast graph (`SetNode('fps')` -> `GetNode('fps')` -> consumer edge rewrite), but gives up silently and emits `raw_call` when it can't trace a pattern it recognizes. Phase 3.5's Block A was the explicit fix for this: enumerate the helper shapes actually present in `ready_templates/sources/community/runexx/*.json` and `ready_templates/sources/community/kijai/*.json`, then extend the resolver. **That work was completed (Phase 3.5 v5 plan `done`/`approved`) but the diff sits uncommitted on the `phase-3-5` worktree.** Until it lands, runexx templates ship with these raw_call helper leaks.

### Category B — community-node classes with positional `widget_N`

```python
power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '1627', ...
    widget_4='',
    model=ltx2attentiontunerpatch,
)
```

The `WIDGET_SCHEMA` doesn't have a curated entry for the class, the schema-provider isn't returning input names for it, and there's no object_info snapshot. So widget aliases fall through to raw positional names. Subagent `a230a8d8` already covered the 6 originally-flagged scratchpads (17 entries, 79 → 0). The 4 additional runexx templates I regenerated *after* that subagent finished pulled in classes it never saw: `Power Lora Loader (rgthree)`, `AudioEnhancementNode`, `AudioNormalizeLUFS`, `AudioConcat`, `BlockifyMask`, `LoadVideosFromFolder`, `NormalizeAudioLoudness`, `AILab_Qwen3TTSVoiceClone`, `LTXVAddLatentGuide`, `LTXVPreprocessMasks`, `ImageBatchExtendWithOverlap`, `LTXVImgToVideoInplaceKJ`, plus raw_calls into `MelBandRoFormerModelLoader`, `FaceSegment`, `AudioNormalizeLUFS`, `AudioEnhancementNode`. Same shape of fix, fresh class types.

### Category C — entire classes emit as `raw_call` because no typed wrapper exists

`AudioEnhancementNode` shows as `raw_call('AudioEnhancementNode', '1904', widget_0=...)` because **there is no `class AudioEnhancementNode` in `vibecomfy/nodes/*.py`**. The pack hasn't been ingested into vibecomfy's typed registry. Even with a widget-schema entry, the call would still be `raw_call(...)`. The fix is structural — a generalized **wrapper-generation pipeline** that ingests installed custom-node packs (or their object_info snapshots) and produces typed Python wrappers automatically. Doing this by hand for every new pack/class is the current pattern; it doesn't scale and is the root cause of "this class isn't supported."

## The three sweeps

### Sweep 1 — Land Phase 3.5 (Category A)

**Worktree:** `phase-3-5 worktree`
**Branch:** `phase-3-5` (uncommitted modifications — verified by `git status`)
**Plan state:** `done` / `approved` (review verdict `approved` with a known-false-positive `DIFF_SIZE_SANITY` pre-check)

**Steps:**
1. Inspect the uncommitted diff in the phase-3-5 worktree. Stage by deliverable (A: helper resolution + tests; B: triage doc; C: dispositions; D: wanvideo bugfix; E: re-emits; F: tests; G: docs).
2. Commit as a small number of atomic commits with clear messages tied back to the DC-1..DC-6 done criteria.
3. PR against `scratchpad-emitter`. CI green → merge.
4. Verify the helper-resolver changes by regenerating any runexx template — `grep -c "raw_call('GetNode'\|raw_call('SetNode'\|raw_call('Reroute'" out/scratchpads/decorator_ltx2_3_runexx_*.py` should drop to 0 for the patterns Phase 3.5 enumerated.
5. The decorator branch `feat/ready-template-decorator` then needs to pick up Phase 3.5 via a rebase or merge from `scratchpad-emitter`.

**Acceptance:** Phase 3.5 commits land on `scratchpad-emitter`. Decorator branch carries them. Helper-elimination patterns Phase 3.5 prep enumerated produce 0 raw_call helper leaks on the corresponding runexx templates.

**Anti-scope:** No new Block A patterns invented mid-sweep — only commit what Phase 3.5 prep enumerated. Don't touch ltx2_3_runexx_*.py "manual" markers; those dispositions are part of what we're landing.

### Sweep 2 — Widget-schema gap-fill on the additional runexx templates (Category B)

**Worktree:** `feat/ready-template-decorator` (or fresh branch on top of it once Sweep 1 lands).
**Target set:** the 4 runexx templates that still have widget_N after `a230a8d8`'s pass:
- `decorator_ltx2_3_runexx_lipsync_custom_audio.py` (38)
- `decorator_ltx2_3_runexx_video_to_video_extend.py` (17)
- `decorator_ltx2_3_runexx_talking_avatar_qwen_tts.py` (29)
- `decorator_ltx2_3_runexx_music_video_low_ram.py` (54)

**Steps:** identical pattern to `a230a8d8` — enumerate (class_type, widget_N) pairs, source canonical names from object_info / custom-node INPUT_TYPES / pack source, extend `WIDGET_SCHEMA` (or `WIDGET_SEMANTIC_NAMES` where appropriate) with inline source citations, regenerate the 4, confirm `grep -c "widget_[0-9]"` returns 0 across them.

**Acceptance:** zero unresolved widget_N across all 9 runexx templates. Existing test suite passes.

**Anti-scope:** Don't extend WIDGET_SCHEMA for class_types whose field names can't be verified against object_info or source — mark `TODO: schema unknown` instead. Don't try to generalize the wrapper-gen pipeline here (that's Sweep 3).

### Sweep 3 — Generalized custom-node-wrapper generation (Category C)

This is the structural fix and the one with the biggest payoff. The pattern today:

- Pack discovered → human reads INPUT_TYPES → human hand-writes a `vibecomfy/nodes/<pack>.py` typed wrapper → human keeps it in sync with upstream changes.

The generalized fix: a **discovery + codegen pipeline** that does this automatically.

**Design (proposed — subagent should refine):**

1. **Discovery sources** (in precedence order):
   - Live ComfyUI `/object_info` from a running server (most accurate, most expensive)
   - Cached `vibecomfy/porting/cache/object_info/*.json` snapshots
   - `vibecomfy/porting/object_info/` static snapshots (`object_info/<pack>@<commit>.json`)
   - Reading `custom_nodes/<pack>/**/*.py` for `INPUT_TYPES` declarations (offline; covers packs not in object_info)

2. **Codegen output:** generate `vibecomfy/nodes/<pack_slug>.py` files that mirror the typed wrappers in `vibecomfy/nodes/core.py` / `vibecomfy/nodes/wanvideowrapper.py`. One class per ComfyUI node class. Type-hinted inputs based on INPUT_TYPES annotations.

3. **CLI surface (proposed):**
   ```
   python -m vibecomfy.cli nodes generate-wrappers <pack-slug> [--source object_info|live|source] [--out vibecomfy/nodes/]
   python -m vibecomfy.cli nodes generate-wrappers --all  # everything in custom_nodes.lock
   python -m vibecomfy.cli nodes wrapper-status            # which packs have wrappers, which don't
   ```

4. **Drift detection:** existing `nodes drift <pack>` CLI already exists — extend to compare generated wrapper signatures against upstream INPUT_TYPES.

5. **Schema collocation:** the generator should also produce `WIDGET_SCHEMA` entries for the class types it covers, eliminating the need for Sweep-2-style hand-curation on future packs.

6. **Determinism + lock:** generated files should be regenerable byte-identical given the same `object_info` snapshot. The snapshot's SHA goes in a header comment so drift is observable in diffs.

**Branch:** fresh branch `feat/generalized-wrapper-codegen` from `main`. Independent of Sweeps 1+2 because it touches `vibecomfy/nodes/` and a new CLI command, not the emitter/helpers/widget_schema.

**Acceptance:**
- `nodes generate-wrappers <pack>` produces typed wrappers for at least 3 demo packs (rgthree-comfy, ComfyUI-LTXVideo, a third installed pack).
- Regenerating the 4 stubborn runexx templates after running `generate-wrappers --all` produces typed calls instead of raw_call for the packs that have object_info coverage.
- Existing tests pass; new tests cover codegen determinism + INPUT_TYPES → signature accuracy.
- Doc `custom_node_wrapper_codegen.md` written explaining the pipeline + the precedence order + how to regenerate.

**Anti-scope:**
- Not building a "discover packs from PyPI / GitHub" feature. Only operate on packs already in `custom_nodes/` or `custom_nodes.lock`.
- Not touching emitter logic or helper resolution. Pure ingestion + codegen.
- Not auto-running on every commit. Manual `generate-wrappers` invocation; lockfile tracks output state.
- Not solving the "object_info missing" problem for packs that aren't installed — those still need manual or future-discovery solutions.

## Sequencing

- Sweep 1, 2, 3 can run **in parallel**:
  - Sweep 1 owns the `phase-3-5` worktree + commits to `scratchpad-emitter`.
  - Sweep 2 owns `feat/ready-template-decorator` (or a branch on top), touches `widget_schema.py` only.
  - Sweep 3 owns a fresh `feat/generalized-wrapper-codegen` branch from `main`, touches `vibecomfy/nodes/` + a new CLI.
- After all three land: a regen of the 9 runexx templates should produce zero `widget_N`, zero raw_call for `GetNode/SetNode/Reroute`, and typed wrappers for the packs Sweep 3 covers.

## Done state — verifiable

```bash
# After all 3 sweeps merged into the decorator branch:
for tpl in $(ls ready_templates/video/ltx2_3_runexx_*.py); do
    name=$(basename "$tpl" .py | sed 's/^/video\//')
    python -m vibecomfy.cli port reemit "$name" --out "out/scratchpads/clean_$(basename $tpl)" 2>&1 | tail -1
done

# All three should return 0:
grep -c "widget_[0-9]"          out/scratchpads/clean_*.py | grep -v ":0$" | wc -l
grep -c "raw_call('GetNode'"    out/scratchpads/clean_*.py | grep -v ":0$" | wc -l
grep -c "raw_call('Reroute'"    out/scratchpads/clean_*.py | grep -v ":0$" | wc -l
```

When this returns three zeros, the decorator-template emitter is "done" by the standard of the runexx corpus.

---

## Outcomes — what landed on 2026-05-26

### Sweep 1 — Phase 3.5 land (BLOCKED → REDIRECTED)

DeepSeek subagent inspected the phase-3-5 worktree per brief, found the diff didn't match scope, refused to commit. **Block A (helper resolution) was never actually implemented by Phase 3.5** despite the plan showing `done`/`approved`. See forensic below — different work landed under the Block A label.

What IS in the phase-3-5 worktree (and is independently useful, could land as a separate PR):
- ~37 template regens
- `tests/fixtures/canonical_parity_baseline.json` (~25K line delta)
- `template_index.json` (636 lines)
- `vibecomfy/registry/ready_template.py` (new file)
- 3 new test files: `test_ready_template_helpers.py`, `test_port_reemit.py`, `test_public_input_naming.py`

Block A as scoped in Phase 3.5 is still outstanding. Sweep 3's wrapper-codegen pipeline overlaps part of that scope (typed wrappers reduce raw_call leakage) but does NOT cover helper-elimination (`GetNode`/`SetNode`/`Reroute` rewriting). True Block A is still a separate task.

### Sweep 2 — Widget gap-fill (LANDED — PR #19)

DeepSeek subagent. Branch `fix/widget-alias-gapfill-runexx` (commit `b1d8381`) targets `fix/widget-alias-resolution-decorator`.

- 17 new `WIDGET_SCHEMA` entries with object_info / source citations
- Classes: `MelBandRoFormerModelLoader`, `AudioNormalizeLUFS`, `AudioEnhancementNode`, `LTXVPreprocessMasks`, `LTXVAddLatentGuide`, `LTXVAudioVideoMask`, `ImageBatchExtendWithOverlap`, `LTXVImgToVideoInplaceKJ`, `LoadVideosFromFolder`, `AudioConcat`, `GetImageRangeFromBatch`, `VHS_LoadVideo`, `NormalizeAudioLoudness`, `AILab_Qwen3TTSVoiceClone`, `FaceSegment`, `BlockifyMask`, `MarkdownNote` (TODO)
- 138 widget_N → 0 on the 4 originally-stubborn templates; tests pass
- ~27 residual widget_N in `LoadVideosFromFolder` / `LTXVAddLatentGuide` overflow positions (these classes are covered but templates carry more positions than the curated entries)

### Sweep 3 — Generalized wrapper codegen (LANDED — PR #20)

Claude Opus subagent. Branch `feat/generalized-wrapper-codegen` (6 commits).

- **New modules:** `vibecomfy/porting/wrapper_discovery.py`, `vibecomfy/porting/wrapper_codegen.py`
- **Precedence:** live `/object_info` → cached → static snapshot → AST-of-source (NEVER `exec` pack code — pack imports may bring in torch/cuda)
- **New CLI:** `nodes generate-wrappers`, `nodes wrapper-status`, `nodes generate-widget-schema`
- **329 typed wrappers** generated across 3 demo packs: rgthree-comfy (24), ComfyUI-LTXVideo (75), ComfyUI-KJNodes (230)
- **Determinism confirmed:** byte-identical re-generation
- **Doc:** `custom_node_wrapper_codegen.md`
- **17 new tests** + existing suite passes
- **Caveats:** AST can't recover runtime-evaluated combo enums (`folder_paths.get_filename_list(...)`) — those need live/cache discovery

### Forensic — why Phase 3.5 shipped a wrong-scope diff

Root cause chain (DeepSeek forensic subagent):

1. **Prep crashed silently** on `area-1-helper-shape-enumeration` with `"Prep research field 'code_refs' must be a list"` (the exact bug commit `d59f2557` fixes — but that commit wasn't on megaplan main when Phase 3.5 ran; landed today as part of PR #51).
2. **Plan v1 filled the vacuum by reframing scope** — "extend emitter.py" became "verify emitter.py" — an unverified assertion.
3. **Critique v1 caught the unverified assertion**; plan v2 acknowledged but kept the verification posture. T5 "verified" 734/734 helpers already handled. T6 was conditional ("if T5 finds gap, patch") and became a no-op.
4. **Critique v2 had 12 open significant flags** but none flagged scope drift from brief.
5. **Gate said PROCEED** (accept_tradeoff on all 12).
6. **Review approved** because criteria were **plan-derived**, not **brief-derived**. The `PRECHECK-DIFF_SIZE_SANITY` flag fired (right signal) but was dismissed as false-positive.

**Recommended systemic fix:** brief-touchpoints-vs-diff check at review. Enumerate the brief's `Touchpoints` section, confirm every named file appears in the diff, and if missing the reviewer must either justify (with evidence linking to a plan step that legitimately eliminated it) or issue `needs_rework`. Today the review criteria are plan-derived and always pass when the plan executes faithfully — but **"faithful to the plan" ≠ "faithful to the brief"** when the plan itself redefined scope mid-flight (e.g., during a prep failure).

---

## PR queue as of 2026-05-26

| PR | Repo | What | State |
|---|---|---|---|
| megaplan #51 | megaplan | adaptive-critique schema fix | ✅ MERGED |
| megaplan #52 | megaplan | layered defense (loud fallback + startup probe + CI guard + doctor subcommand) | awaiting review |
| vibecomfy #18 | vibecomfy | m1-renderer-gate (chain milestone) | awaiting merge → unblocks m2 |
| vibecomfy #19 | vibecomfy | Sweep 2 widget gap-fill (138→0) | awaiting merge to widget branch |
| vibecomfy #20 | vibecomfy | Sweep 3 wrapper codegen + new CLI | awaiting review |

Plus three working branches:
- `feat/ready-template-decorator` — base decorator emitter + spacing fix (decorator subagent + a796a8e1)
- `fix/widget-alias-resolution-decorator` — a230a8d8's widget cleanup (the foundation PR #19 builds on)
- worktree `phase-3-5` — Phase 3.5 partial diff, not landed

## Remaining outstanding tracks

- **(a)** Residual ~27 widget_N — `LoadVideosFromFolder` + `LTXVAddLatentGuide` overflow positions. Small.
- **(b)** Megaplan brief-vs-diff systemic check (forensic recommendation). Medium.
- **(c)** Actual Block A implementation — helper-node elimination for `GetNode`/`SetNode`/`Reroute` patterns Phase 3.5 was supposed to extend but didn't. Medium. Sweep 3's wrapper codegen reduces raw_call leakage from typed-wrapper-missing causes, but does NOT address helper-elimination.
- **(d)** Salvage the non-Block-A Phase 3.5 worktree pieces as a separate PR (template regens, parity baseline, ready_template registry, new tests). Small/medium.

User triage pending on which of (a)/(b)/(c)/(d) to fire next.

---

## Session 2 outcomes — 2026-05-26 13:00–13:30 UTC

This session's job was to land the PR queue from session 1 + fire Block A. Hit
substantial CI infrastructure rot along the way (none of it new — main's CI was
silently partial-and-broken for weeks). All foundation pieces landed; the rest
is delegated to background watchers and a subagent.

### What merged

- **megaplan #52** — layered adaptive-critique defense (loud fallback, startup
  probe, CI guard, `doctor --adaptive-critique` subcommand). Merged at 12:34 UTC.
- **vibecomfy #18** — m1-renderer-gate, the foundation milestone of the
  scratchpad-emitter epic. Merged at 12:34 UTC.
- **vibecomfy #21** — CI resilience fix (see below for the full chain). Merged
  at 13:26 UTC after 9 push/CI cycles.

### vibecomfy #21 — the CI resilience fix (the bone of this session)

The first push triggered a `setup-uv@v3` CDN flake; the user's
`/go-all-the-way` invocation correctly refused the "GitHub's CDN flaked, wait
it out" hedge and pushed for the root. The audit found *six* layered issues,
all pre-existing:

1. **`astral-sh/setup-uv@v3` SPOF.** Every CI run depends on
   `codeload.github.com` serving the action tarball at job start. One CDN flake
   = entire CI fleet down. Fixed by replacing with direct
   `curl https://astral.sh/uv/install.sh | sh` + `$GITHUB_PATH` write.
2. **5 of 6 workflow files missing from main.** Only `strict-ready.yml` was on
   `origin/main`; `ci.yml`, `parity.yml`, `e2e_matrix.yml`, `nightly-runpod.yml`,
   `schema_freshness.yml` had been on feature branches only. PRs whose source
   branches lacked these silently skipped most CI (e.g. #20 only ran Strict
   Ready). Landed all six on main.
3. **`uv sync --extra dev` silently dropped 3 of 5 dev extras** on Ubuntu Python
   3.12 (`hypothesis`, `pytest-cov`, `pytest-rerunfailures`) — installed pytest
   and pytest-asyncio fine. Reproduced as `uv pip install` not honoring extras
   either. Fixed by switching to `uv venv --seed` + `.venv/bin/python -m pip
   install -e ".[dev,runpod-launch]"`.
4. **`pyproject.toml` dev extras incomplete on main.** Only `pytest` and
   `pytest-asyncio` declared; the other three lived on feature branches
   indefinitely. Added all five to main's pyproject.
5. **`uv run X` resyncs the venv before every call**, uninstalling the dev
   extras that pip just installed (verified in the parity log:
   `Uninstalled 9 packages in 10ms` right before the `python -m` command).
   Replaced every `uv run X` with `.venv/bin/X` to bypass.
6. **Pre-existing app-code orphans tripped CI:** `tests/test_models_registry.py`
   and `tests/test_runpod_runner.py` import `runpod_lifecycle.PodGuard` which
   doesn't exist in the pinned v0.1.1; their `importorskip` lines guard the
   wrong symbol. `tools/regenerate_snapshots.py` and
   `tools/check_canonical_parity.py` exist only on feature branches and have
   never landed on main. Mitigations: `--ignore` the two test files, drop
   `parity.yml` from the fix PR, drop the snapshot-check step from `ci.yml`,
   all with comments noting "re-add when the dependent script lands."

**Final result:** PR #21 green — `Strict Ready: success`, `ci: success` with
1006 passed, 20 skipped, 6 deselected, coverage XML uploaded.

### What's in flight (background watchers + subagent)

- **Block A megaplan** — running in subagent `a6bd8ae0`. Profile
  `partnered`/`full`/`--with-prep`/depth `medium`/critic `low`. Phases
  observed: init → prep → plan → critique → revise (iter 2) → critique →
  gate → finalize → execute (last observed). Plan dir
  `.megaplan/plans/block-a-helper-node-20260526-1436/`. Brief at
  `.megaplan/ideas/scratchpad-emitter/block-a-helper-elimination.md`.
- **PRs #19 and #20** — pushed CI fixes onto both branches (`#19` via
  fast-forward of cherry-picked workflow files; `#20` already had them via
  `gh pr update-branch`). Both reopened to retrigger CI. Background watcher
  `bcwzkxeeh` will report when both complete. **Caveat:** #19 has *unresolved*
  merge conflicts with main on app code (`scratchpad_loader.py`, `testing/*`,
  `workflow.py`). Workflow files were applied by direct file replacement; the
  app-code merge is still owed and can't be done blindly.

### Lessons worth remembering (not in the strategy doc; in feedback memory)

- **CI infra rot on main is invisible until first full run.** Workflows on
  feature-branch-only live on with broken assumptions. The fix found four
  separate orphan dependencies (3 dev extras, 1 workflow's script, 1 ci
  step's script, 1 parity workflow's script). Pattern: feature branch makes
  CI improvements + adds dependencies → never lands on main → CI on main
  references things it can't find.
- **`uv run` ≠ "run in the venv pip created."** It re-syncs from pyproject's
  declared deps and removes anything else. For projects where pip is the
  source of truth, use `.venv/bin/X` directly.
- **"GitHub's CDN flaked" is rarely the right diagnosis** if every workflow
  in your repo hits the same third-party action on every run.

### Open threads for next session

1. **Watch `bcwzkxeeh`** for #19/#20 CI outcome — merge whichever land green.
2. **#19's app-code merge conflicts** with main need real resolution
   (not a CI fix concern): `scratchpad_loader.py`, `testing/__init__.py`,
   `testing/_pytest_plugin.py`, `testing/fixtures.py`, `workflow.py`.
3. **Block A megaplan** is independently progressing; review its execute-phase
   output when the subagent reports terminal state.
4. **PodGuard import error** in test_models_registry / test_runpod_runner
   should be fixed in a small app PR (bump runpod-lifecycle pin OR correct
   the `importorskip` to guard `runpod_lifecycle.PodGuard` not `dotenv`).
5. **Re-add parity.yml + tools/check_canonical_parity.py** as one combined PR
   when ready. Same for `tools/regenerate_snapshots.py` + ci.yml's snapshot
   step.
