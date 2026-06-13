# Agent-Edit Fidelity: the Concrete-Tree / Diff-over-Original Design

Status: design + Phase-1 prototype. Companion to
`../local_agent_text_to_graph_blockers.md` (the evidence) and
`e2e-real-browser-tier.md` (the runbook).

## 1. The root cause (one sentence)

VibeComfy has **one** round-trip, built for *authoring clean canonical templates*
(lossy by design), and it is being used for a fundamentally different job —
*editing a user's live graph* (which must be faithful). Those are opposite
contracts.

Authoring **wants** to: normalize model paths, strip annotation nodes, resolve
helper/virtual-wire nodes, drop schema-default widget values, rebuild nodes from
the schema, renumber ids. Editing must **preserve** every one of those.

### Compiler framing
VibeComfy's `VibeWorkflow` IR is an **abstract tree**: it discards "trivia" —
exact positions, link ids, path separators, annotation nodes, helper structure,
widget ordering, unknown-node specifics. Source-preserving tools (refactorers,
codemods — libCST, Roslyn red/green trees) established long ago that to edit and
have everything you *didn't* touch return byte-for-byte, you need a **concrete
(lossless) syntax tree**, not an abstract one. We are doing codemods with an
abstract tree. That is the whole problem.

## 2. Every observed blocker is a symptom of this one cause

| Blocker (see blockers.md) | The lossy authoring behavior behind it |
|---|---|
| A — model path `\`→`/` (7/7 LTX) | emitter normalizes loader widget strings |
| B/C — Power Lora / Get/Set lowering | emitter resolves helper/virtual nodes to core nodes |
| B7 / PreviewAny, E / MarkdownNote | emitter strips `UI_ONLY_CLASS_TYPES` |
| B8 — dotted v3 inputs, widget misalign | ingest maps `widgets_values` positionally vs schema |
| B13 — malformed full-file output | agent returns a whole replacement file |
| B12 — guard no-ops on first edit | preserve-machinery keyed on `vibecomfy_uid` users lack |
| parity gate hard-blocks real workflows | gate asks "is the full round-trip canonically equal?" |

## 3. Target architecture — five deep solutions

**S1. A lossless / concrete editing IR (the foundation).**
Carry each node's *original raw UI blob* (widgets, link ids, properties, position,
path strings, verbatim class) as preserved trivia on the IR node. Emit replays a
node from its trivia unless that node was edited. Path-normalization,
default-stripping, widget-remap, helper-lowering, and annotation-stripping become
*structurally impossible* for untouched nodes — they are never reconstructed from
schema.

**S2. Apply = `original + targeted delta`, never "regenerate the whole graph".**
The candidate UI is the verbatim original with a minimal patch for only the
changed nodes/widgets/edges. Falls out of S1. Flips the core question from "can we
faithfully reconstruct this entire graph?" (impossible in general — there is
always a node pack we don't model) to "can we apply this one change?" (always
tractable).

**S3. Edits as a bounded operation list, not a full-file rewrite.**
The agent emits operations — `set_widget(node, field, value)`, `connect(...)`,
`add_node(...)` — a small, inspectable, validatable delta applied to the concrete
tree. This is how a human edits (you don't redraw the graph to change a prompt).
Makes the delta explicit, kills the full-file fidelity ceiling and the
`from __future__` class of failures (B13).

**S4. Separate the agent's READ VIEW from the APPLY SUBSTRATE.**
Reading-fidelity and apply-fidelity are different requirements; conflating them is
the original sin. Keep the lossy, schema-canonical Python as the view the agent
*reads* (great for comprehension; the agent doesn't care about path separators).
Edits apply to the lossless substrate, not back through the lossy view.

**S5. Replace the parity-equivalence oracle with a delta-scope guard.**
"Candidate == original everywhere outside the intended delta" is *true by
construction* under S1+S2, so the gate becomes a cheap assertion, not a lossy
oracle. Retire canonical-parity from the *edit* path (keep it for *authoring*).
Stamp stable identity at ingest so the guard engages on the first edit (B12).

The deepest payoff: **node-pack-agnostic forever.** You never again chase
"workflow X uses node Y we don't model." If you didn't edit it, it round-trips.

## 4. You've already half-built this

The diff-over-original machinery exists but is **inert or misordered**:
- `pin-opaque` (`widget_shape_fence.py`, `ui_emitter.py`) already copies a node's
  raw UI verbatim — but only as a *fallback for "complex" nodes*, applied *after* a
  lossy regeneration, instead of being the default.
- `layout_store.py` already preserves prior geometry.
- `guard_emit(original_ui, candidate_ui, snapshot_delta)` (`refuse.py`) already IS
  the delta-scope guard (S5).
- `compute_field_delta` already computes the changed fields.

Two defects keep it from working on a user's first edit:
1. It is keyed on `vibecomfy_uid`, which a hand-authored canvas lacks → empty
   scope → guard no-ops (B12). Verified: 0/9 uids on the reference graph.
2. Pin-opaque is a fallback, not the default → unchanged nodes are still
   regenerated through the lossy emitter.

So this is **completing and reorienting existing machinery**, not a rewrite.

## 5. Phased migration (corrected after the 2026-06-01 Codex adversarial review)

> **Sense-check correction.** An earlier draft ordered P2 (verbatim-preserve)
> before P3 (op/delta interface). That is **unsound**: while the agent returns a
> *full-file replacement*, "which nodes are unchanged" is **unknowable** — a node
> missing from `IR'` could be a user deletion, a convert omission, a scratchpad
> strip, or a loader/lowering change. You cannot preserve "unchanged" nodes until
> the edit declares its delta. So the **explicit edit contract is the foundation**,
> not a late phase. Revised order:

- **Phase 0 — Identity at ingest (diagnostic).** Stamp a stable `vibecomfy_uid`
  onto the original UI so matching/guarding is *possible*. Keep it gated OFF until
  preservation exists — on its own it only turns `guard_emit` into a tripwire.
  *Prototype landed (gated).* **Known defect (Opus review):** the prototype stamps
  a *copy* for the guard **after** `python_before` is rendered from un-stamped IR
  (`emitter.py:2582` only emits `_uid=` when a uid exists), so the agent's read
  view and the guard's scope are anchored *differently*. Phase 1 fixes this by
  stamping the substrate **before** the view is rendered.
- **Phase 1 — The address-mapping contract (the real foundation).**
  > **Deepest-root correction (2026-06-01 Opus review).** An explicit op-list is
  > necessary but is only a *proxy* for the true root: a stable, bidirectional
  > **view-coordinate ⇄ substrate-address** mapping. The agent reads a *lossy
  > canonical* view (renumbered ids, `widget_N` aliases, lowered helpers, flattened
  > dotted inputs) but must target the *verbatim substrate*. An op named in
  > view-coordinates can fail to resolve — or resolve to the wrong field — onto the
  > substrate. So Phase 1 is the *mapping*, not just the op-list:
  - (a) Stamp `vibecomfy_uid` onto the **original substrate before rendering the
    read view**, so every node carries its uid as a visible handle in the Python
    the agent edits (`_uid=` always emitted).
  - (b) Op targets are `(uid, schema_field)` pairs, with an explicit
    **view→substrate resolver that fails LOUDLY** when a view-coordinate (a
    `widget_N` alias, a lowered helper, a flattened dotted input) cannot resolve to
    exactly one substrate node/field. "No op references an unresolvable target" is
    the core Phase-1 test.
  - (c) Land the **raw-UI-outside-delta editing corpus now** (not a late phase), so
    the API-space weakness of `guard_emit` is caught before Phase 3 leans on it.

  This makes the intended delta *declared in resolvable coordinates* (not inferred
  by diffing `IR'`), and independently fixes B13.
- **Phase 2 — Apply the delta to the ORIGINAL substrate.** Apply the declared ops
  to the verbatim original UI JSON (or a concrete IR that carries the original node
  blobs as trivia) — **not** to a UI regenerated from `IR'`. Unchanged nodes are
  copied byte-for-byte. Kills A/B/C/E/B7/B8 wholesale. Canonical Python stays the
  agent's **read view** only.
- **Phase 3 — Verbatim-preserve + delta-scope guard, then enable identity.** With
  the candidate now faithful, turn on identity (Phase 0) and `guard_emit`; the
  guard asserts "candidate == original outside the declared delta" — true by
  construction. **Note:** today `guard_emit` compares only API `class_type`+`inputs`
  — it must be extended (or complemented) to assert *raw UI* preservation
  (positions, annotations, widget order), or those losses slip through.
- **Phase 4 — Retire convert-parity from the edit path.** Replace the convert-stage
  parity hard-fail with the delta-scope guard (keep parity for *authoring*).
  Unblocks the LTX-class workflows.

### Architecture framing (per the review): one substrate, two policies
Not two independent round-trips (that invites divergence + double-maintenance).
**One concrete substrate with two policies:** *authoring* may canonicalize
(normalize paths, prune, resolve helpers); *editing* may only apply an explicit
delta over the verbatim original.

### The deepest invariant (Opus review) — the bar every phase serves
> Every op the agent emits must name a substrate node-and-field by an identity
> that (a) exists in the read view the agent was given **and** (b) resolves to
> exactly one node/field in the verbatim original — and that identity must be
> stamped **before** the view is ever rendered.

If this invariant holds, op-based editing, verbatim-preserve, and the delta-scope
guard all become sound; if it does not, they fail silently (an op targets the
wrong field, or the guard greenlights a wrong-field apply). Phase 1 exists to
establish exactly this invariant.

### What clears the LTX workflows
They fail at **convert** (parity False + schema-less), upstream of emit/guard, so
identity/guard work (Phase 0/3) does not touch them. They clear at **Phase 4**,
which depends on Phases 1–3 (a declared delta applied to the original, faithfully
preserved) being in place first.

## 6. Verification strategy

- Authoring stays guarded by the existing 47-workflow parity corpus.
- Editing gets a NEW corpus: for N real workflows (incl. the LTX set and the
  Gemini/ByteDance graph), assert "candidate == original outside the asserted
  delta" for a scripted edit (e.g. change one prompt widget). This is the S5
  property and the only correctness bar editing needs.
- Per-phase gate: no rise in the authoring corpus failures; the editing corpus
  monotonically improves (more workflows pass "untouched-outside-delta").

## 7. Phase 1 prototype — implemented + findings (2026-06-01)

Implemented in `agent_edit.py`: `_stamp_identity_on_original(graph, workflow)`
stamps the IR's stable uid onto a COPY of the original UI (`state.guard_original_ui`),
which `_stage_emit` passes to `emit_ui_json(guard_original_ui=...)`. Gated behind
`VIBECOMFY_AGENT_EDIT_IDENTITY=1` (default OFF).

Verified:
- **uid survives the round-trip**: ingest IR uid == round-tripped IR' uid for 8/8
  shared nodes, and uid == litegraph node id (stable). So the candidate's uids
  match the stamped original → a real guard scope.
- **Guard scope 0 → N**: `_uid_to_litegraph_id(original)` goes from **0** (user
  canvas has no `vibecomfy_uid`) to **9** after stamping the reference graph. The
  delta-scope guard can now engage on a first edit.
- **Default OFF keeps everything green**: 332 focused tests pass with the flag off.

Why it is gated OFF (the findings that define Phase 2 + the env work):
1. **Guard engaged ⇒ lossy candidate refused.** With identity on, `guard_emit`
   actually runs and (correctly) refuses candidates that diverge from the original
   outside the intended delta — because the candidate is still produced by the
   LOSSY regeneration path. Confirmed: a simple save-prefix edit fixture now
   returns `ok=False`. This is the guard doing its job; it is unsafe to enable
   until **Phase 2 (verbatim-preserve)** makes the candidate faithful, and until
   `snapshot_delta` reliably captures the edited fields.
2. **Guard needs the ComfyUI converter importable.** `guard_emit` →
   `_load_convert_ui_to_api()` imports `comfy.component_model.workflow_convert`
   (torch-free, from the pinned `vibecomfy[comfy]` dependency). In the live ComfyUI server it is NOT
   importable (`ModuleNotFoundError: comfy.component_model`) even though
   enough that a local checkout exists — it needs the converter importable in the active Python. **Launcher
   fix required** (`scripts/run_local_agent_comfy.sh`) before the guard can run in
   the server.
3. **LTX-class workflows block upstream of the guard.** They fail at the *convert*
   stage (parity False + schema-less), so Phase 1 (an emit-side enabler) does not
   clear them. They need **Phase 4** (retire convert-parity for editing) — which
   in turn relies on Phase 1 (guard engaged) + Phase 2 (faithful candidate) +
   finding #2 (converter on path).

Net (corrected by the Codex review — see §5): identity (now **Phase 0**) is *not*
the foundation; it only makes guarding *possible* and, alone, turns `guard_emit`
into a tripwire. The real foundation is **Phase 1 — an explicit edit contract**,
because "unchanged" is unknowable after a full-file rewrite. Ordered unlock:
**Phase 1 (declared delta / op-list)** → **Phase 2 (apply delta to the original
substrate)** → **finding #2 (vendor path) + enable identity + extend `guard_emit`
to raw-UI fidelity** → **Phase 4 (retire convert-parity for edit)**. This prototype
remains valuable as the gated identity mechanism Phase 3 will switch on.
