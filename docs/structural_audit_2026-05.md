# VibeComfy structural audit — May 2026

**Method:** 10 parallel DeepSeek-V4-Pro subagents, each given one analytical lens and
only its slice of the repo to read (28–216 tool calls each). The verbose file-reading
stayed in each subagent's context; only conclusions were synthesized here. Three headline
claims were independently re-verified against the working tree before inclusion.

**Result:** Every one of the 10 lenses returned the same verdict — **"strained."** Not one
"healthy," not one "broken." That uniformity is itself the finding. The architecture's
*skeleton* is sound (the two-layer model holds, the IR is a real funnel, the CLI dispatcher
is clean, abstractions are mostly in the right place). What is strained is everything around
the skeleton: god-modules, duplication, hand-maintained data that has drifted from reality,
and a near-total absence of enforcement keeping any of it honest. **This is maturation debt,
not rot** — the system grew faster than its guardrails.

## Per-lens verdicts

| # | Lens | Verdict | Sharpest finding |
|---|------|---------|------------------|
| 1 | IR core (`workflow.py`) | Strained | `inputs`/`widgets` split leaks ComfyUI internals + has a merge-order bug; `finalize_metadata()` is destructive/non-idempotent |
| 2 | Layer-2 boundary (blocks/patches/ops) | Strained | Boundary mostly holds, but `resize_schema.py` is a non-`Patch` hiding in `patches/`; `controlnet.py` reimplements block machinery |
| 3 | Emitter / codegen (`porting/`) | Strained | 3,719-line god-module; verified broken output in `z_image.py` |
| 4 | CLI (`cli.py` + `commands/`) | Strained | Clean dispatcher, but `port.py` (1,347) & `nodes.py` (919) are god-files; ~30% of `--json` bypasses the `emit()` helper |
| 5 | Runtime (embedded/server/runpod) | Strained | `VibeSession` protocol exists but unused; embedded/server are two separate paths; RunPod not in `run()` at all |
| 6 | Router / ops verb layer | Strained | Routing is 5 hardcoded rules; ~60% of the verb surface raises `KeyError` |
| 7 | Templates / corpus pipeline | Strained | Manifest trails disk (5 orphan templates); materialize script cited in docs doesn't exist |
| 8 | Node-spec system (`nodes/`) | Strained | ~12,280 LOC (54% of `nodes/`) is dead code from a deprecated generator |
| 9 | Testing strategy | Strained | Emitter/IR well-covered; runtime/eval layer is a blind spot; marker bug silently drops runpod tests |
| 10 | Plugins / node+model registry | Strained | Collision semantics contradict each other across ops/blocks/patches/routes |

## Cross-cutting themes (the real signal)

These appeared in *multiple* independent lenses, which makes them structural rather than local.

### Theme 1 — Hand-maintained data shadows that drift from code/disk/runtime (5 lenses)
- `workflow_corpus/manifests/coverage.json` trails disk by 5 templates (lens 7)
- `_ROLE_CLASSIFICATION` dict hand-maintained, missing custom-node classes → no section comments on LTX templates (lens 3)
- `KNOWN_NODE_PACKS` computed at import time, stale if the lockfile changes afterward (lens 10)
- `router_rules.py` — every model is a hand-edited code entry (lens 6)
- node specs have no CI sync guard against the live runtime (lens 8)

### Theme 2 — No enforcement / CI gates (the flip side of Theme 1)
- no freshness check wired into CI for templates vs corpus (lens 7)
- generator never deletes stale files → 12K LOC ghost accumulated (lens 8)
- no CI job runs any RunPod test, and a `conftest.py:85` `and`-should-be-`or` bug means `--runpod-full` *deselects* regular runpod tests (lens 9)

### Theme 3 — God-modules begging for decomposition (4 lenses)
`porting/emitter.py` 3,719 · `runtime/session.py` 1,379 · `commands/port.py` 1,347 · `nodes/comfyui_kjnodes.py` 8,713 (and dead).

### Theme 4 — Duplication across module seams
`session.py`↔`config.py` (6 duplicated functions/classes), `inspect.py`↔`analyze.py` trace logic, `controlnet.py`↔block machinery, `UI_ONLY_CLASS_TYPES` defined twice.

### Theme 5 — Half-finished unifications
The `VibeSession` protocol exists but isn't used for dispatch; RunPod is a CLI silo outside `run()`; plugin collision rules differ per registry. The *intent* to unify is visible in the code — it just wasn't carried through.

## Verified concrete bugs (fix-now, not opinion)

Independently confirmed against the working tree:

1. **`ready_templates/image/z_image.py` is broken** — line 73 `steps=770044821593082` (a seed value in the steps field) and line 74 `cfg='randomize'` (a `control_after_generate` string leaked into a float field). The emitter mismapped subgraph call-kwargs and this shipped into a curated template. *Check whether other generated templates share the leak.*
2. **`scripts/materialize_ready_templates.py` does not exist** — older agent docs cited it as the template-generation entry point (step 7 of "Adding a new workflow"). The real path is `cli port convert`, one at a time.
3. **~12,280 LOC of dead node-spec code** (`comfyui_kjnodes.py`, `comfyui_ltxvideo.py`, `rgthree_comfy.py`) — referenced only by `scripts/demo_wrapper_codegen.py`, nothing in production.

High-confidence but not separately re-verified (precisely located by the audits): IR `inputs`/`widgets` merge-order bug (lens 1), `conftest.py:85` marker logic (lens 9), `_common.py` double-prompt-set hack (lens 6).

## Prioritized remediation

**Tier 1 — cheap, high-leverage:**
- Fix the `z_image.py` emitter kwarg-mapping bug (and grep other templates for the same leak).
- Delete the 12K dead-node-spec lines + add stale-file cleanup to the generator.
- Fix the `conftest.py` marker bug.
- Reconcile the agent skill with reality (remove/rewrite the missing-script references).
- Add the 5 orphan templates to `coverage.json`.

**Tier 2 — structural payoff (~1–2 weeks each):**
- **Build the missing enforcement layer** (addresses Themes 1+2 at once): a single
  CI gate that asserts manifest↔disk, node-specs↔runtime, and template↔corpus consistency.
  Highest-value investment — converts five silent-drift problems into loud failures.
- Decompose `emitter.py` and `session.py`; de-dup `session.py`↔`config.py`.
- Make the hand-maintained registries data-driven (router rules, `_ROLE_CLASSIFICATION`).

**Tier 3 — finish the unifications:** make `run(runtime="runpod")` real via a third
`VibeSession` impl; unify the two `_run_untracked` paths; make plugin collision semantics
consistent across all five registries; wire the missing ops verbs (i2i/edit/inpaint/audio).

## Caveats

- Subagent line numbers were accurate where spot-checked but may drift as the tree changes;
  treat them as pointers, not citations.
- This was a *breadth* sweep (10 lenses, read excerpts). It is strong on architecture and
  drift, weaker on deep per-function correctness. See the companion methodology note for
  detection techniques this pass did **not** cover (cyclomatic complexity, import cycles,
  near-miss duplication, dependency direction, churn-vs-complexity hotspots).

---

# Part 2 — Second sweep (different slicing axes)

**Method:** 12 more subagents (9 DeepSeek-Pro judgment + 3 DeepSeek-Flash mechanical sweeps),
deliberately sliced on axes the first pass was blind to: end-to-end seam tracing, per-artifact
drift audits, cross-package duplication, dependency direction, change-amplification probes, and
tree-wide mechanical pattern inventories. Headline claims re-verified against the tree.

## The escalation: the emitter mismap is a bug *family*, not a one-off (VERIFIED)

The first sweep found `z_image.py` shipped with `steps=<seed>` / `cfg='randomize'`. The trace
agent (j2) found the same root cause — a **positional desync between the `input_items` and
`widgets_values` arrays** in `porting/emitter.py` (`_subgraph_instance_widget_values` ~line
2765, feeding `_subgraph_call_kwargs` ~2648 and `_node_kwargs` ~3348) — corrupts a whole class
of templates. Spot-verified examples beyond z_image:

- `video/ltx2_3_runexx_talking_avatar_qwen_tts.py:242-244` — `voice=986337553816914` (seed-magnitude
  int where a path belongs), `unload_models=116899311982882` (where a bool belongs), `seed='randomize'`
  (a `control_after_generate` string where an int belongs). **Runtime-breaking.**

Honest scope: **~8 templates carry runtime-breaking value corruption** (wrong-typed values in
*named* params); a further ~12 carry cosmetic `widget_N='fixed'` unresolved-alias leaks (often
harmless — `RandomNoise(control_after_generate='fixed')` is actually correct). One shared root
cause. **This is the single highest-priority finding in either sweep** — curated, shipped
templates are silently wrong.

## Why it shipped: the safety net is wrapped in `except: pass` (VERIFIED, the key connection)

Mechanical sweep f2 found `porting/convert.py:315-370` wraps a **~55-line parity-validation
block** (compile → import → build → compare against source) in `except Exception: pass`. The
check that exists *specifically to catch emitter-fidelity bugs like z_image* silently discards
its own failures. This links Theme 2 (no enforcement) directly to the headline bug: the gate is
present but disarmed. Fix this one handler and the bug family becomes visible.

f2 found **15 silently-swallowed handlers** in production (8× `pass`, 3× `continue`, plus
message-string filters). Most dangerous: `convert.py:368` (above), `session.py:744`
(`_is_benign_embedded_cleanup_exception`, string-matched), `porting/lint.py:492` (block-import
failures hidden).

## Silent-discard seams (j1) — user intent vanishing without error

The runtime trace found 5 boundary defects; the worst three:
1. **`set_prompt`/`set_seed` silently no-op for unregistered inputs.** `set_input` (`workflow.py:244`)
   parks unmatched names in `metadata["unbound_inputs"]`; `compile()` never reads it. Because
   `z_image.py`'s `finalize({})` registers no public inputs, `wf.set_prompt("x"); run(wf)` via the
   *Python* API succeeds, returns outputs, and ignores the prompt — **no warning, no error**. (The
   CLI `--prompt` path guards this; the Python path does not.) Most dangerous seam found.
2. **`compile()` drops edges whose source was a stripped UI/helper node** (`workflow.py:486`) instead
   of rewiring through them — yet `validate()` doesn't skip those nodes, so a workflow validates clean
   and compiles broken.
3. **`run()` vs `run_embedded()` diverge on schema validation** — embedded passes `cache_only=True`
   (`session.py:295`), so on cache miss it skips validation entirely; `run()` fetches live schema and
   validates. Same workflow, different acceptance.

## Fragile substring class-detection is systemic (f3) — ~97 occurrences

Node behaviour is inferred from `class_type.lower()` substring matching all over the tree, not from
schema. Worst concentration: `runtime/eval.py:164-188` (a 12-branch cascade deciding *output media
type* by substring — `AudioPreview`→preview-not-audio, `VideoSampler`→LATENT-not-VIDEO), plus
`emitter.py` model-family classification (`:608-630`) and `templates.py`/`analysis/graph.py`. A new
custom-node name or a reordered branch silently misclassifies.

## Drift artifacts — quantified, with a ready-made fix pattern (j3/j4/j5)

- **coverage.json is a trailing shadow:** 6 orphan ready-templates on disk with no row (up from 5
  last sweep — it grows monotonically), 1 indexed external workflow uncovered, **0 enforcement gates**.
- **models.yaml is the weakest registry link:** all ~50 `node_pack` references use a naming scheme
  (`wan_wrapper`, `ltx`, …) **disjoint** from `CustomNodePack.name` (`ComfyUI-WanVideoWrapper`, …),
  validated nowhere — a typo stages files under a ghost label silently. `KNOWN_NODE_PACKS` is computed
  at import time and read by 5+ runtime/tool sites (stale-cache risk).
- **`sources sync` indexes are a staleness liability:** gitignored yet tracked;
  `external_workflow_index.json` already stale (36 vs 38 files); `node_index.json` structurally empty
  off-machine; `asset_manifest.json` orphaned (no writer). **`template_index.json` is the lone
  well-guarded one — it has `refresh_template_index.py --check`.** That `--check` pattern is the
  template to clone for the enforcement layer Tier 2 calls for.

## Dependency layering is aspirational (j7)

The Layer-1 IR core **`workflow.py` imports the `porting/` service layer** (`:9-10`, used in 6 methods);
`contracts/surface.py` and `porting/workbench.py`→`commands/` also point the wrong way. No cycles *yet*,
but `workflow.py` (36× fan-in) ↔ `porting/` is one import from a cycle, and the high count of
function-body deferred imports (`emitter.py` ×4, `convert.py` ×4) shows the team already working around
the tension instead of fixing the direction.

## Cross-package duplication ~340 LOC (j6)

Clones the per-subsystem sweep couldn't see because they span packages: **topological sort
reimplemented 4×** (`porting/naming.py`, `emitter.py`, `testing/dry_run.py`, `analysis/graph.py`, ~122
LOC), **`is_api_link`/`_is_link` 9× across 8 files** (~60 LOC; `emitter.py:3021`↔`parity.py:49` are
character-identical and must-stay-in-sync), `UI_ONLY_CLASS_TYPES` 4×, the variable-naming pipeline
forked private copies in `emitter.py` vs `naming.py`, and `REPO_ROOT` recomputed in 8 files. Most are
S-effort consolidations into `_graph_utils.py` / a shared `paths.py`.

## Hardcoded node IDs (f1)

Concentrated in 3 LTX-tied production files. Worst is **`contracts/ltx_first_last.py`** — ~40
occurrences, ~25 distinct hardcoded ids (`"98"`,`"125"`,`"136"`…) embedded directly in contract
validation, coupling the whole module to one workflow's exact node numbering. Also `patches/ltx_lowvram.py`
(12) and `scripts/runpod_matrix_remote.py` (23).

## Change-amplification — a *calibrated* abstraction verdict (j8/j9)

Measured rather than asserted, and it splits cleanly:
- **Adding `audio.t2a` end-to-end = 4 touch points** (1 new file + 2 registration sites + 1 router rule).
  The ops/router core is fully generic. **This is a *good* abstraction** — the verb surface is
  incomplete only because nobody wired it, not because it's hard. (Refines first-sweep lens 6.)
- **Adding a 4th runtime = 8 scattered edits across 4 files.** `VibeSession` is referenced *once* as a
  type hint, with no factory/registry/dispatch — **a label, not an abstraction.** A `dict[str, type]`
  session factory collapses it from 8 edits to 2.

## Revised top priorities (both sweeps merged)

1. **Fix the emitter positional-desync** + re-emit the ~8 corrupted templates. *(was Tier-1; now #1 overall)*
2. **Disarm `convert.py:368`'s `except: pass`** so the parity gate actually fails — this is what let #1 ship.
3. **Make `set_input` loud** (warn/raise on unbound) — closes the most dangerous runtime seam.
4. **Build the enforcement layer**, cloning `refresh_template_index.py --check`: gates for coverage.json↔disk,
   models.yaml `node_pack`↔catalog, and `sources sync` index freshness. *(still the highest structural ROI)*
5. Then the structural cleanups: emitter/session decomposition, the ~340 LOC dedup, fix the
   `workflow.py`→`porting` layering, replace substring class-detection with schema lookups, and the
   `VibeSession` factory.
