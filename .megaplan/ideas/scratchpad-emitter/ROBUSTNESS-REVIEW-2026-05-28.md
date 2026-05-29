# Scratchpad-emitter epic — robustness review & revised plan (2026-05-28)

**Method:** 14 independent subagents (6 DeepSeek grounding + 8 Claude cloud: identity, round-trip,
parity-oracle, red-team, layout, editor-journey, epic-structure, subgraphs/furniture), each grounded
in the *current* code on `epic/excellence/m3-seams-ir` (not the stale May-25 design docs).
**Reframe driving the review:** the maintainer set the **primary user = editor-first ComfyUI user**
(lives in the graph editor, shares `.json`, positions are sacred). Scope unchanged (Python IR ↔ UI
JSON round-trip with position); no server. "Don't shrink scope; add depth."

---

## TL;DR — the verdict

The epic's M1 ("renderer + identity + parity") is **merged but does not deliver a position round-trip
at all**, and the *locked architecture* ("Python is source of truth; UI JSON is a disposable,
best-effort view; preserve = match against the prior JSON on re-emit") **is the wrong foundation for
an editor-first user.** Every reviewer independently reached the same conclusion and the same fix:
**replace "match-on-re-emit" with a durable persistent node identity (a minted UUID) + first-class
persisted layout/furniture.** This is an architecture change, not a tuning pass — and it must be
settled before M2/M3 build further.

---

## What is actually true in the code today (verified, with cites)

1. **Positions never survive a round-trip.** Ingest *does* capture the full litegraph node into
   `VibeNode.metadata["_ui"]` (`ingest/normalize.py:95` → `porting/convert.py:144`) — so `pos`/`size`/
   `groups`/`mode`/`color` reach the in-memory IR. But (a) the **Python emitter never serializes them**
   to the `.py` file (it reads `_ui` only for widget aliases/output names), and (b) **`emit_ui_json`
   ignores `_ui` for geometry** and always calls `_stub_layout` — a 4-column, 400px grid
   (`porting/ui_emitter.py:113-125, 560, 669`). **Every emit re-grids.** Verified end-to-end repro:
   input `pos [111,222]/[999,888]` + a named group → emitted `.py` has neither; `emit_ui_json` returns
   `{5:[0,0], 6:[400,0]}`, `groups: []`.

2. **`ir_node_id` is a write-only stamp.** Written at `ui_emitter.py:631` (`= node.id`); **nothing in
   ingest ever reads it back.** On re-ingest, identity resets to the litegraph integer id, and
   `_next_node_id()` is `max(numeric)+1` (`workflow.py:637-639`). So `ir_node_id` cannot carry identity
   across JSON→Python→JSON. *Correction to the design's fear:* there is **no live renumbering** —
   in-session ids are append-only/stable; the instability is at **re-execution** and **at ingest**.

3. **`port export --to ui` does not exist.** `_cmd_port_export` rejects any `--to` value but `json`
   (`commands/port.py:430`) and only emits API JSON; `emit_ui_json` is imported but never called
   (`port.py:39`). The headline CLI verb is unwired.

4. **Export uses the *mutable* schema provider.** `_cmd_port_export` builds `AuthoringSchemaProvider`
   (`port.py:433`), whose precedence puts mutable `out/cache` object-info **ahead** of the pinned index
   (`schema/provider.py:295-349`). → widget order / socket types can differ **between machines**, which
   breaks any prior-JSON merge. The deterministic `ConversionSchemaProvider` exists and is already wired
   for *convert* (`port.py:918`) but not for export. (Per-machine determinism = a one-line provider swap
   plus the schema-less-node gap below.)

5. **Silent furniture loss far beyond positions** (corpus counts from the survey of 47–50 workflows):
   - **groups** hardcoded `[]` (`ui_emitter.py:742`) — **34/48** have groups.
   - **subgraphs**: ingest never reads `definitions` (grep count 0); `_emit_definitions` reads
     `metadata["definitions"]` which is **always empty** → dead code. **19/47** ship subgraphs (incl.
     official `z_image`, `ltx2_3_*`, all flux2/qwen edits). Inner subgraph ids are **destroyed at ingest
     → not recoverable** (resolves M1's open question: *no*). Worst case: `ltx2_3_runexx_music_video_low_ram`
     has **10 subgraphs**, several near-clones (`samplers` vs `samplers_8b36a85a`).
   - **Notes/MarkdownNotes** stripped — **32/47** have them. **Reroutes** resolved away — nodes the user
     can *see* vanish. **bypass/mute** (`mode≥2`) → re-emitted as **active** (`mode:0`): **22/47** —
     this is **semantic corruption**, not just cosmetics. Colors, collapsed state: dropped.

6. **The parity gate is 100% self-referential offline.** `offline_parity_check` compares
   `_normalize_ui_to_api(emit_ui_json(wf))` to `compile("api")` — both sides VibeComfy code, and a test
   (`test_parity_gate_never_imports_comfy`) *enforces* that ComfyUI is never imported. It would pass a
   swapped-widget-order emitter (both sides make the same mapping error). The canonical form itself is
   sound (Weisfeiler-Lehman isomorphism, `testing/canonical.py:65`), but the *normalizer* is shared. The
   only real-ComfyUI gate (`test_porting_ui_emitter.py:672`, `@pytest.mark.comfy`) runs on **one**
   workflow and only asserts "didn't crash." There is **no** independent object_info-backed gate today.

7. **Duplicate nodes are common** (≥6 templates with same-class+same-widget twins; cloned subgraphs).
   The design's "reject-on-collision → treat as new → auto-place" rule therefore **rips pinned nodes onto
   the grid** on the most common real graphs — the exact opposite of preserving position.

8. **M2 layout is over-invested for this user.** The loader→sampler→save **spine fails ~60% of the
   corpus** (12 zero-sampler edit/t2i graphs, 17 multi-sampler, plus *serial* sampler chains the design
   didn't anticipate). The fanin-difference stage partition is non-total under parallel samplers. Real
   node widths reach **1775px** (stub assumes 320) and canvases span **8–11k px** (spiral-ray cap was
   2000px) → **guaranteed overlap**. And the editor-first user mostly wants **their own** layout back
   (preserve), not a clever fresh one. Fresh layout only runs on first export or `--fresh`.

9. **Excellence-epic drift is mostly favorable.** M1-net-correctness fixed the widget-value desync;
   M2b made `ConversionSchemaProvider` the canonical, documented, wired provider; `workflow.py` no longer
   imports `porting/` (helpers extracted to `_workflow_helpers.py` etc.). In-flight `contracts/ir.py`
   (uncommitted) *hardens* identity guarantees (helps). **Risks:** announced-but-not-landed `set_input`
   strictness (ValueError) and `_next_node_id` **gap-filling** would make auto-ids *less* predictable —
   another reason not to anchor identity on `ir_node_id`. All design file:line refs are stale by 5–40 lines.

---

## The convergent recommendation: persistent identity + persisted layout

Replace the "best-effort match against prior JSON" model with **identity that survives by construction**:

1. **Mint a durable UUID once per node and persist it in the litegraph `properties`.**
   ComfyUI/litegraph round-trips unknown `properties` across editor saves — so a `vibecomfy_uid` stamped
   in the JSON survives the user's editor edits *for free*. On ingest, **read it back** if present, mint
   if absent. This makes editor→Python→editor identity hold by construction, not by guessing.
2. **Make geometry + furniture first-class and persisted, keyed by UUID.** Capture `pos`/`size`/`groups`/
   notes/reroutes/`mode`/`color` at ingest. Persist via a **sidecar `<file>.layout.json` keyed by UUID**
   (keeps the `.py` clean and diff-stable; survives loss of the original JSON when committed alongside the
   Python). Keep the *execution* IR runtime-shaped; furniture rides in the sidecar/`metadata`.
3. **Emit reads persisted layout by UUID first; only genuinely-new UUIDs get auto-placed.** This makes
   the "preserve" path correct independent of how M2's fresh layout behaves.
4. **Demote the structural hash to a one-time legacy-migration aid.** For pre-UUID files, hash-match once,
   then *mint and persist* a UUID so the next round-trip is exact. On collision, **prefer keeping a prior
   position over rejecting/scattering** — never auto-move a node that has any prior-position candidate.
5. **Answer "what to do with the NEW positions" explicitly:** the user's latest editor JSON is
   **authoritative for layout**; every ingest captures its `pos`/furniture into the UUID-keyed store
   (newest editor wins). Python owns *structure*; the editor owns *layout*.

---

## Revised milestone structure (authoritative — see the m2..m6 idea files + `scratchpad-emitter.yaml`)

**Maintainer clarification (2026-05-28):** the goal is to **MAKE THE ROUND-TRIP WORK** — preserve the
position/furniture data *as well as possible* when it exists (best-effort *maximized*, graceful
degradation; never required), place new nodes in sensible spots, AND produce a clean layout for
Python-authored code that has **no positioning metadata at all**. So fresh layout is **first-class and
required** (it is the primary path for the ~50 authored ready templates) — it is made *robust and
simple*, not demoted/cut. Final order puts layout **before** preserve, because preserve reuses layout's
constrained new-node placement primitive.

- **M0 (gate, not a milestone):** don't fork until the IR-contract sprint (`m3-seams-ir`) lands and
  convert/emitter/contracts stop moving (dirty now). Confirm `set_input`-strictness and `_next_node_id`
  gap-filling status before relying on any id behavior.
- **M2 — Durable identity + lossless ingest (NEW; the real foundation).** Mint/read-back a per-node UUID
  (stamped in litegraph `properties`, so it survives editor saves); stop dropping `pos`/`size`/`groups`/
  notes/reroutes/`mode`/`color`/subgraph `definitions` — route them into a uid-keyed layout store
  (sidecar). *The keystone the merged "M1" skipped.* Persistence is optional; absence degrades to M4.
- **M3 — Emitter completion + independent oracle.** Wire `port export --to ui` (currently dead); switch
  export to the pinned `ConversionSchemaProvider`; emit furniture verbatim (incl. `mode`/bypass);
  recovery report; stand up the object_info-backed gate (Layer 2) as a **blocking** CI gate.
- **M4 — Fresh layout engine (REQUIRED) + constrained placement.** The path for no-metadata code, and
  the new-node placement primitive M5 reuses. Built robust-and-simple: longest-path layering over the
  full DAG (after SCC collapse) + **fixed ~520px column pitch** + one lane per weakly-connected component
  + height-from-widget-count sizing + bounded spiral-ray for new nodes. Deterministic golden test. Drop
  the spine-first backbone, fanin-stage partition, fixed canvas cap, and per-node width prediction.
- **M5 — Position/furniture-faithful preserve (HEADLINE).** Restore pos/size/furniture by UUID (exact,
  contractual); legacy structural-hash only as a one-time bridge that mints+persists a uid; on duplicate
  collision do stable min-drift assignment, never scatter; new nodes via M4 placement; preserve is
  default, `--fresh` overrides. Losing a uid-matched position is a **gate failure**.
- **M6 — Productionize/docs/tests.** Rewrite the "disposable, best-effort view" framing — wrong for this
  user. Document: editor owns layout, Python owns structure, round-trip works and preserves when it can.

## Independent verification (ship Layer 2 immediately — it needs no GPU)
- **Layer 0:** keep offline self-consistency, but **rename its guarantee** ("emitter↔normalizer agree", not "correct").
- **Layer 1:** differential vs `compile("api")` using an **independent** read-back derived from the
  `object_info` cache (`porting/object_info/`), NOT the shared `_normalize_ui_to_api`.
- **Layer 2 (blocking, offline):** validate every emitted node against real `object_info` (widget
  count/order, socket types, required inputs) using the committed `@runpod-snapshot.json`.
- **Layer 3 (release gate):** deepen the `convert_ui_to_api` comfy test to corpus-wide + `canonical_equal`
  + object_info input-name check (RunPod).
- **Layer 4:** headless litegraph "does it open" smoke.
- **Property/fuzz:** random valid IR → emit → independent read-back == `compile("api")`; widget-count &
  slot-range invariants. Catches the duplicate/collision cases the fixed corpus misses.
- **Position-fidelity oracle (M3′):** emit → perturb positions → round-trip → assert unchanged nodes keep
  exact `pos`/`size`; a renamed/removed id is treated as new (not snapped to a stale position).

## Three decisions to settle BEFORE any milestone
1. **Identity = minted UUID carried through the round-trip** (recommended), or the current `max+1`
   `ir_node_id`? Everything downstream forks here; the code says the current id cannot survive ingest.
2. **Does `port convert` become position/furniture-preserving** (recommended), or stay lossy? This
   contradicts "Python pure" — resolve the contradiction explicitly rather than letting M3 paper over it.
3. **Conflict precedence** when both a prior JSON and new editor positions exist (the maintainer's literal
   "what do we do with the new positions"): recommend **newest editor layout wins**, captured per-UUID at
   ingest. Define it now.

## The single highest-leverage change
Stop treating the UI JSON as derived. Make layout a first-class, UUID-keyed, persisted artifact that
VibeComfy owns end-to-end (sidecar + UUID-in-properties), captured at convert and restored at emit. This
fixes positions, groups, bypass-state, *and node existence* (reroutes/notes) at once, and reduces the
widget-default and collision issues to non-events.

---

# CLARITY PHASE ADDENDUM (2026-05-28, +5 investigations: K1-K5)

After the maintainer reframe ("make it WORK; preserve as well as possible; new nodes in sensible places;
must also work for code with no positioning metadata"), 5 focused investigations pinned the load-bearing
assumptions. Net: **the architecture holds**, with one real correction (bypass/`mode`) and one process gate.

### K1 — Keystone CONFIRMED ✅ TRUE: a `uid` in `properties` survives the editor round-trip.
litegraph `LGraphNode.serialize()` deep-clones the **entire** `properties` dict (no whitelist) and
`configure()` restores all keys; ComfyUI itself relies on this (`Node name for S&R`, `cnr_id`, `ver`).
Top-level `extra` is an open schema field (`extra.ds`, `extra.node_versions`) — our `extra.vibecomfy`
breadcrumb survives too. ComfyUI's integer node `id` is **not** stable (reassigned on add/remove/reorder);
there is no built-in node UUID — so `properties["vibecomfy_uid"]` is the correct, idiomatic mechanism.
**Only caveat:** hand-editing the JSON *outside* ComfyUI can strip it → that's exactly the structural-hash
fallback case (M5). The whole "uid survives saves for free" premise is sound.

### K2 — M0 gate: NOT YET SATISFIED (process), but adding `uid` is architecturally clean. ⚠️
- The m3-seams-ir sprint work is **100% uncommitted** (T1-T15 in the working tree; T16-T26 pending).
  **PR #26 targets `fix/emitter-revert-block-a-regressions`, not main**, and carries only the init commit.
  Suite is **red at collection** (2 pre-existing import/registration errors). → Do not fork until: commit
  T1-T15, retarget PR to main, land T16-T26, and get the suite green.
- Two announced IR changes **have landed in the working tree**: `set_input` now **raises ValueError** for
  unregistered inputs (was `unbound_inputs` fallback); `_next_node_id` now **gap-fills** (lowest-unused,
  was max+1). Gap-fill means **integer-id reuse on delete+add is a live hazard** → confirms identity must
  key on `uid`, never the int id. `VibeNode` is a plain `@dataclass(slots=True)` and `metadata` is
  unconstrained; `contracts/ir.py` imposes no shape limit → **add `uid` as a real `VibeNode` field**
  (NOT an int-id-keyed metadata entry). `finalize_metadata`/`compile` never renumber nodes, so a `uid`
  field survives both. *(M2 idea file updated accordingly.)*

### K3 — Inertness TRUE for layout, **FALSE for `mode`/bypass** — the one real correction. 🔧
- **Proven** (offline repro): mutating `pos/size/groups/color/flags/properties/title` is byte-identical in
  `compile("api")`. compile's read-set is only `class_type`, `widgets`, `inputs`, `edges` — never
  `metadata`. So pure layout is inert; carrying it in a store is safe.
- **BUT `mode` (bypass=4 / mute=2) is execution-relevant.** Real ComfyUI `convert_ui_to_api` drops muted
  nodes and **rewires** around bypassed ones; VibeComfy's offline `_normalize_ui_to_api` ignores `mode`
  entirely, so a bypassed node currently round-trips as **active = silent semantic corruption**.
  **Correction to the plan:** `mode` is NOT layout furniture — it must be captured into the **execution
  IR**, and M3 must define a real bypass policy (and the offline gate can't see it, so this only surfaces
  against the object_info / real-comfy gate). *(M2 + M3 idea files updated.)*
- Also: `groups[]`, `extra.ds`, `state.lastRerouteId`, subgraph `definitions` are **graph-level**, never
  in per-node `_ui` → the store needs a **graph-level section**, not only per-node entries.

### K4 — Independent object_info gate: GO today, offline, no GPU. ✅
Real committed snapshot is at **`vibecomfy/porting/cache/object_info/`** (not `porting/object_info/` — that
dir is a decoy), `index.json` = 1401 classes, pinned via `provenance.json` (per-pack locked commits).
Executable-node coverage across corpus is **~95%+**; the ~71 "misses" are subgraph-UUID instances,
`SetNode`/`GetNode`/rgthree layout nodes, and uninstalled experimental packs (IAMCCS) → **warn-and-skip
loudly with a max-skip budget**. Read via `ObjectInfoIndexSchemaProvider(root)` **directly** (bypass the
gitignored `node_index.json` so a stale local copy can't shadow it). Treat `@stub.json` entries as
schema-less too. This gate shares no code with `_normalize_ui_to_api` → genuinely breaks the self-reference.

### K5 — Subgraph round-trip: feasible, with 3 must-dos. ✅(conditional)
Corpus definitions already carry object-style inner links + inner `pos`/`size`; `_emit_definitions`
(`ui_emitter.py:311-339`) emits a near-valid block **if** `metadata["definitions"]` is populated.
Must-dos: (1) **deep-copy `raw_workflow["definitions"]` into metadata BEFORE the resolver runs**
(`convert.py:~186`) — the helper resolver deletes inner nodes in place; (2) inner IR is flattened/renumbered
at ingest, so treat carried definitions as the **authoritative inner-layout store**, not something rebuilt
from the flat IR; (3) the subgraph **UUID regenerates on every editor save** → inner-node preserve identity
must key on **`(subgraph name + content-hash) : inner-source-id`**, not the UUID. Clone ambiguity is a
non-issue: each clone is a distinct def with exactly one instance. *(M2 + M5 idea files updated.)*

### Net effect on the plan
Architecture stands. Three concrete changes propagated into the milestone files: (a) `uid` is a real
`VibeNode` field; (b) `mode`/bypass is execution IR + an explicit M3 bypass policy, not layout; (c) the
layout store has a graph-level section, definitions are deep-copied pre-resolver, and inner-node identity
keys on name+hash, not UUID. Plus the M0 process gate (commit + retarget PR #26 + green suite) before forking.

---

# PHASE A ADDENDUM (2026-05-28): two gaps closed before declaring excellence

A holistic self-audit found the revised plan was well-grounded but not yet excellent: a determinism
contradiction, a backloaded delivery shape, and an un-reviewed synthesis. Two resolved here; the third
(adversarial re-review) follows.

### U1 — uid-determinism fork (FIRST attempt — ⚠️ SUPERSEDED by Phase B below, kept for the record).
Phase A's first answer was a **content-addressed** uid: `blake2b(workflow_id‖class_type‖structural_key)`
where structural_key fell back to the Weisfeiler-Lehman label in `testing/canonical.py`. **Phase B's
adversarial review proved this self-defeating and it has been REPLACED** — see "FATAL" in the Phase B
addendum. (Two errors in the first attempt, both corrected: (1) it claimed "zero `uuid4` in the codebase
— grep 0"; that is FALSE — `runtime/session.py:316,501` call `uuid.uuid4().hex`, and `ui_emitter.py:130`
already uses `uuid5`. The point survives narrowly: there is no nondeterministic id on the *emit/identity*
path. (2) the WL label folds in widget values + a 4-hop neighborhood and isn't even exposed per-node, so
it changes a node's uid on ordinary widget/wiring edits — exactly the wrong behavior.) The live decision
is the extrinsic assigned-once scheme in the Phase B addendum and `m2-identity-and-lossless-ingest.md`.

### V1 — early vertical slice ADDED (`m1_5-walking-skeleton.md`).
The epic proved the round-trip only at M5. New **M1.5 walking skeleton** (after M0, before M2) cuts the
thinnest end-to-end path — uid + capture pos -> convert -> emit -> restore-by-uid — on `z_image`, with
everything else stubbed. Its stubs ARE the later milestone seams (M2-M6 thicken one dimension each, zero
rework). Retires the keystone risk (does the uid survive a REAL ComfyUI save) in milestone one; acceptance
is the actual loop run by hand with the real editor as oracle (not a tautological test, per maintainer).

### Standing instruction recorded
Maintainer: do NOT write tests just to make something pass — focus on holistic improvement. Reflected in
M1.5 (acceptance = real-editor demo) and U1 (proving oracle = the real round-trip property, not an
implementation-detail unit test).

### Remaining before "holistically excellent": Phase B adversarial re-review of THIS synthesis (in progress).

---

# PHASE B ADDENDUM (2026-05-28): adversarial re-review of the synthesis — one fatal flaw found & fixed

Two independent red-team reviewers attacked the REVISED plan (not the old one). They **converged on the
same fatal flaw**, which is strong signal it's real. All findings now corrected in the milestone files.

### FATAL (both reviewers) — content-addressed uid was self-defeating. FIXED.
Phase A's "deterministic uid = `blake2b` over the WL canonical label" was wrong: `testing/canonical.py`'s
WL label folds in **widget values + neighbor labels (4 hops)**. So editing a widget (prompt/seed/cfg) or
inserting a node would change the uid of that node AND its neighbors -> the position is lost on exactly the
edits users make most. **You cannot derive a stable identity from the thing that changes.**
**Fix (applied to M2, chain header, M1.5, M5):** identity is **extrinsic and assigned-once**, carried IN
the artifacts — `properties["vibecomfy_uid"]` (survives editor saves, K1) + an explicit **`uid=` kwarg in
the `.py`** (same mechanism as the existing `id="98"`; the Phase-A "never write uids to `.py`" rule was the
root error). Minting (first appearance only) uses a stable EXTRINSIC seed (explicit id / authored source
order / litegraph-id-at-ingest) -> deterministic for no-metadata code AND edit-invariant. WL/structural
hashing demoted to the **M5 legacy bridge only** (nodes with no carried uid). New guard criterion in M1.5
+ M5: change a widget -> position must NOT move.

### SERIOUS — sidecar doesn't travel. FIXED.
ComfyUI users share a single `.json` (or PNG, or paste) — a sidecar never travels. **Fix (M2):** the
emitted `.json` is **self-describing** (uid in `properties` + `pos` on the node + furniture in native
slots); JSON<->JSON needs no sidecar. The sidecar exists ONLY as the `.py` form's regenerable layout cache,
never a source of truth. New criterion (M5): "user B gets only the `.json`" round-trips with full fidelity.

### SERIOUS — M1.5-before-M2 double-built identity. FIXED.
M1.5 and M2 both "owned" the uid field/store. **Fix:** M1.5 OWNS and FREEZES the interface contracts
(`VibeNode.uid` field, resolver signature, store/`uid=` schema); M2 is reframed as "**broaden** M1.5," not
"introduce identity." Also: M1.5's subject changed from `z_image` (which ships subgraphs — a stubbed
dimension) to a verified **flat** workflow; minting in M1.5 uses the dumbest stable extrinsic id.

### MODERATE — mode/bypass contradicted "compile byte-identical." FIXED.
**Decision (M2+M3):** M2 captures `mode` as data without changing compile (byte-identical holds); M3 makes
`compile("api")` **drop/rewire bypassed+muted nodes to match ComfyUI by design**, and the parity gate is
updated to EXPECT it. Precise invariant: *byte-identical for graphs with no bypassed/muted nodes; matches
ComfyUI's drop/rewire for graphs that have them.*

### MODERATE — object_info Layer-2 oracle oversold. FIXED.
It's provenance-shared (emitter also reads object_info) and warn-skips exactly the schema-less community
nodes most likely to break. **Fix (M3):** Layer 2 is a fast *pre-filter*, not an independence guarantee;
**Layer 3 (real ComfyUI) is the gate of record** for any workflow with schema-less nodes; such round-trips
are marked "layout-verified, widgets-UNVERIFIED" until Layer 3 passes.

### MODERATE — journeys honesty. FIXED.
M6 now names covered vs deferred journeys: PNG-embedded workflows and simultaneous conflicting edits are
**explicitly deferred** (not silently missing).

### Maintainer request folded in: `--main-positions` flag
Added to M3 (flag surface) + M6 (docs): an opt-in `port export --to ui --main-positions` that emits the
**fuller native litegraph metadata** (`extra.ds` viewport, `state` counters, node `order`/`title`, full
`groups[]` geometry) for a file that reopens exactly as the user left it. Lean default stays diff-small and
free of machine-specific canvas state; the flag is the explicit "give me everything" switch and pairs with
preserve (M5). Determinism preserved (absent fields -> fixed defaults, never machine-dependent guesses).

### Verdict after Phase B
The diagnostic work (K1-K5) was always strong; the identity architecture was the heart and it was wrong in
Phase A. With identity re-founded on extrinsic assigned-once uids carried in the artifacts, the self-
describing-`.json` invariant, the M1.5/M2 ownership split, the bypass-compile decision, the honest oracle
framing, and the named-deferral of PNG/conflict journeys — **the plan is now holistically sound.** It
should get ONE more confirmation pass (a re-read by a fresh adversary on the corrected identity model)
before execution, but no known fatal flaw remains.

---

# PHASE C ADDENDUM (2026-05-29): "GO ALL THE WAY" — 5 deeper hunts found a structural hole + a live crash

The maintainer invoked go-all-the-way. Five agents attacked the seams I'd been flinching from (full
edit-matrix, hidden compromises, conflict-merge, weird-comfy edge cases, DX personas). They moved the
verdict from "holistically sound" back to **NOT YET — there is a structural hole and a live crash**.

## 🔴 BIGGEST FINDING — the IR cannot hold the nodes the editor user cares most about.
GetNode/SetNode/Reroute (litegraph "virtual wires") are **resolved away to direct links at ingest**
(`workflow.py:558,868`, `_helper_resolve.py`) before any uid/store/layout logic runs. They never become
`VibeNode`s → **cannot carry a uid or a pos**. The whole identity+preserve architecture is structurally
incapable of round-tripping them. Census: **723 GetNode/SetNode + 11 Reroute across 54 files**; the
music-video monster has **188 of 484 nodes** as Get/Set (some bypassed/named/colored by the user). M1.5
picks a *flat* subject with none of these; M2-M5 never re-add them → a green epic preserves positions on the
toy graph and **silently rewires real graphs into spaghetti**. DECISION REQUIRED: make Reroute/Get/Set
first-class uid-bearing round-trippable IR nodes, OR loudly refuse to claim "round-trip works" for graphs
containing them. Currently neither — silent degradation dressed as the headline.

## 🔴 LIVE BLOCKER — emit crashes on ~30% of the corpus today.
`ui_emitter.py:657` asserts `len(widget_values) <= expected_widget_count`, but ComfyUI's real converter
(`vendor/.../workflow_convert.py:130` `_extra_widgets_after`) legitimately appends trailing slots (seed +
control_after_generate, upload). **17/54 files (~30%: all wan*/ltx2_3*/qwen*) hard-crash `emit_ui_json`.**
Nothing downstream is validatable until reconciled with vendor's rule. Fix at the very start of M3 (or a
pre-M2 hotfix).

## 🟠 SEMANTIC CORRUPTION — bypass/mute re-emits as ACTIVE (quantified: 32/54 files have mode≥2).
Confirmed against vendor: mute=drop, bypass=rewire-through; emitter hardcodes `mode:0`. A re-opened graph
silently executes nodes the user disabled. Also a true execution-semantics change that collides with the
"compile byte-identical" invariant — resolve end-to-end, don't paper over.

## 🟠 DETERMINISM FALSE BY CONSTRUCTION — float positions.
**5080/5280 corpus pos coords are 13-sig-digit floats.** "Byte-identical across machines" + "exact pos
pixel-for-pixel" are untrue for floats through JSON encoders / any layout math. Fix: pin coordinate
canonicalization (round to N decimals + pinned repr) as a contract, or downgrade the claim.

## 🟠 THE IR IS LOSSY BEFORE EMIT RUNS.
`convert.py:130-142` drops unwired optional sockets, collapses widget-vs-input duality, flattens
dict-shaped `widgets_values` (65 nodes). Round-trip can't restore what convert discarded. Per-node
`properties` carry real user state no milestone captures: mask paint-points (`imgData`/`points`), Note
font/color/align, `cnr_id`/`ver` version pins (1526/1590 — dropping de-versions every node + breaks
ComfyUI-Manager), `ue_properties` (389), tab geometry (251). CHEAP FIX (K1: litegraph round-trips arbitrary
properties free): **pass ALL unknown `properties` through verbatim** instead of writing a fresh dict.

## 🟠 WORST-SERVED PERSONA — the AI agent (a stated VibeComfy use case) appears NOWHERE in the milestones.
An LLM edits structurally (triggers `_next_node_id` gap-fill id reuse) with no notion of uids/layout.
Delete node 7 + add one → id 7 reused → M1.5's ingest-id seed mints a uid colliding with the deleted node's
old position → new node snaps to a stale spot. Silent dirty graphs — the exact failure the epic exists to
prevent. FIX: mint uids at `add_node`/`raw_call` time off a **monotonic never-reused per-workflow counter**
(decoupled from the int id); make `uid=` optional/auto-derived; add an agent journey + test to M6.

## ✅ TWO DEFERRED SEAMS — now CLOSED, not deferred.
- **Edit-matrix (C1):** every operation has a defined outcome. Structure always exact (regenerated). Position
  is CONTRACT (exact) for any node seen once; only irreducible+loud BEST-EFFORT rows remain (subgraph inner
  pos, legacy uid-less files, first-emit reorder). **First-mint:** seed from authored source-declaration
  order (NOT the gap-filled int id), then **write the minted `uid=` back into the `.py` on first emit** (same
  mechanism as the existing `_id='9'`). Residual (reorder build() before first emit) is bounded + self-heals.
- **Conflict-merge (C3):** CLOSED via **single-source-per-plane** — Python owns STRUCTURE, editor owns
  LAYOUT, joined on the uid; the planes provably don't overlap (K3) so simultaneous edits aren't a conflict.
  A node *added in the editor* that Python lacks is made safe by **REFUSING to overwrite** (git-style "editor
  ahead" detection); user resolves via `port convert` (import) or explicit `--force-drop`. Never silent loss.

## Revised verdict after Phase C
NOT holistically excellent yet — and now I can name exactly why, with numbers. The architecture is right;
"all the way" needs SIX more decisions baked in: (1) Reroute/Get/Set as first-class round-trippable nodes
or a loud refusal; (2) fix the widget-count crash vs vendor's rule; (3) bypass/mute resolved end-to-end;
(4) float-coordinate canonicalization as a contract; (5) pass-through of unknown `properties` + capture (or
loud scoping) of the IR's pre-emit losses; (6) the AI-agent persona made first-class. With these it is all
the way; without them it's a toy-graph demo wearing a headline.
