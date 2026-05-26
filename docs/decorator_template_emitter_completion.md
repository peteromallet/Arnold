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

Per `CLAUDE.md`: helper/UI nodes are supposed to be stripped during conversion and not survive roundtrip. The helper-resolver `_resolve_helper_nodes_for_emission()` in `vibecomfy/porting/emitter.py` walks the broadcast graph (`SetNode('fps')` → `GetNode('fps')` → consumer edge rewrite), but gives up silently and emits `raw_call` when it can't trace a pattern it recognizes. Phase 3.5's Block A was the explicit fix for this — enumerate the helper shapes actually present in `workflow_corpus/community/runexx/*.json` and `workflow_corpus/community/kijai/*.json`, then extend the resolver. **That work was completed (Phase 3.5 v5 plan `done`/`approved`) but the diff sits uncommitted on the `phase-3-5` worktree.** Until it lands, runexx templates ship with these raw_call helper leaks.

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

**Worktree:** `/Users/peteromalley/Documents/.megaplan-worktrees/phase-3-5/`
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
- Doc `docs/custom_node_wrapper_codegen.md` written explaining the pipeline + the precedence order + how to regenerate.

**Anti-scope:**
- Not building a "discover packs from PyPI / GitHub" feature. Only operate on packs already in `custom_nodes/` or `custom_nodes.lock`.
- Not touching emitter logic or helper resolution. Pure ingestion + codegen.
- Not auto-running on every commit. Manual `generate-wrappers` invocation; lockfile tracks output state.
- Not solving the "object_info missing" problem for packs that aren't installed — those still need manual or future-discovery solutions.

**Implementation:** see [`docs/custom_node_wrapper_codegen.md`](custom_node_wrapper_codegen.md) for the
landed pipeline shape, CLI surface, discovery precedence, and drift workflow.
Modules: `vibecomfy/porting/wrapper_discovery.py`, `vibecomfy/porting/wrapper_codegen.py`;
CLI handlers in `vibecomfy/commands/nodes.py` (`generate-wrappers`, `wrapper-status`, `generate-widget-schema`).

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
