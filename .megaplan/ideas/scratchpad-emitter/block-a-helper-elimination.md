# Block A — Helper-node elimination + primitive inlining

## Outcome

`port convert` MUST eliminate four classes of "edge-only" / "value-only" nodes from
emitted Python and rewrite consumers to bypass them. Today these still appear as
`raw_call(...)` rows in generated templates, which is the bone that Phase 3.5 v5
was supposed to deliver and did not. After this sprint, a re-generated
`ready_templates/video/runexx_*` (and every other regenerated template) MUST contain
**zero** `raw_call('GetNode', ...)`, `raw_call('SetNode', ...)`, `raw_call('Reroute', ...)`,
or `raw_call('Primitive*', ...)` lines — they are rewritten away during conversion.

Concretely, this block in a current runexx template:

```python
primitiveboolean = raw_call('PrimitiveBoolean', '1862', value=False)
reroute = raw_call('Reroute', '1865')
getnode = raw_call('GetNode', '1871', _outputs=('FLOAT',), name='fps')
getnode_2 = raw_call('GetNode', '1919', _outputs=('INT',), name='frames_seconds')
primitiveboolean_2 = raw_call('PrimitiveBoolean', '1929', value=True)
reroute_2 = raw_call('Reroute', '1932', _outputs=('',))
reroute_3 = raw_call('Reroute', '1933', _outputs=('',))
```

…must vanish from the emitted Python. Every consumer of those nodes must have its
input rewritten so the edge points at the **real upstream source** (or, for primitives,
the **literal value** is folded into the consumer's kwargs / registered as a
`PublicInput`).

## Why this is the foundation for everything after

- Phase 3.5 v5 was scoped to ship Block A and shipped the rest of the sprint without it
  (forensic captured in `docs/decorator_template_emitter_completion.md`). The
  worktree's diff did not contain the helper-elimination pass.
- Sweep 2 (widget gap-fill) and Sweep 3 (wrapper codegen) cannot reduce these lines —
  they're addressed by **conversion-time graph rewriting**, not by widget schemas or
  typed wrappers.
- Until this lands, every regenerated ready template carries dead `raw_call` rows that
  (a) are unreadable, (b) defeat strict-ready promotion, (c) confuse downstream
  parity / inspect / coverage tooling, and (d) break the "Python looks like real Python"
  promise of the v2.7 decorator shape.

## Locked decisions (do not relitigate)

- **Strip + rewrite, do not preserve.** Helpers (`GetNode`, `SetNode`, `Reroute`) and
  Primitives (`PrimitiveBoolean`, `PrimitiveInt`, `PrimitiveFloat`, `PrimitiveString`,
  `PrimitiveStringMultiline`, `PrimitiveNode`) MUST be removed from the IR before
  emission and their edges rewritten so consumers connect to the real upstream source
  (or carry the literal value). This is a conversion-time graph transform, not a
  cosmetic emitter post-pass.
- **Resolution lives in normalization, not the emitter.** Today `helpers.py:8` already
  defines `BROADCAST_HELPER_CLASS_TYPES = {"SetNode", "GetNode"}` and
  `helpers.py:34 helper_stripped_nodes` strips them from the dict, but the broadcast
  resolution (rewriting consumers) is incomplete — `Reroute` is not in the helper set,
  Primitives are not in the helper set, and `emitter.py:122-130 FALLBACK_CLASS_TYPES`
  still lists all of these as fallback-emit. The fix extends helper detection and
  resolution to all four classes and removes them from `FALLBACK_CLASS_TYPES`.
- **Primitive inlining strategy is value-first, public-input-second.** For a
  `PrimitiveBoolean(value=False)` feeding one consumer, emit
  `consumer(field=False, ...)` and drop the primitive node. If the primitive is
  reachable through a `PublicInput` (i.e. it carries a `name=` label like
  `fps`/`frames_seconds` from `GetNode`, or sits at a "registered input" location),
  register it via `wf.register_input(...)` and reference the public input symbol
  instead. The decorator-shape templates already carry `PUBLIC_INPUTS = {...}` —
  named Primitives/GetNodes become entries there.
- **`GetNode` + `SetNode` are a broadcast pair.** `SetNode(name='fps')` declares a
  named value; one or many `GetNode(name='fps')` consume it. Resolution: find the
  matching `SetNode` for each `GetNode` (by `name`), follow `SetNode`'s upstream
  source, and rewrite every `GetNode` consumer to point at that source. If the
  `SetNode`'s upstream is itself a Primitive, recurse into primitive inlining.
- **`Reroute` is a 1-in-1-out passthrough.** Rewrite each consumer's edge from
  `Reroute` to the `Reroute`'s upstream source. Reroutes can chain (`Reroute →
  Reroute → ...`) — resolve transitively.
- **Idempotent + ordering-safe.** The resolver MUST handle chains and forks:
  `Reroute(Reroute(GetNode))` resolves through all three; `GetNode` feeding multiple
  consumers updates every consumer. Run resolution to a fixed point before emission.
- **Strict-ready becomes the gate.** `port check --strict-ready-template` MUST escalate
  any remaining `GetNode`/`SetNode`/`Reroute`/`Primitive*` in an emitted template to a
  hard error. Today they are tolerated as helper diagnostics — that tolerance moves to
  "input only, never output."
- **Roundtrip documentation update.** `CLAUDE.md` already states helper/UI nodes are
  stripped during conversion and do not survive JSON→Python→JSON roundtrip. After this
  sprint, primitives behave the same way — document it.
- **No new public surface.** All work lands inside `vibecomfy/porting/` (normalize,
  helpers, emitter, port-check, lint). No new CLI subcommands, no new template API,
  no new public functions on `VibeWorkflow`.

## Scope (IN)

- Extend helper detection in `vibecomfy/porting/helpers.py`:
  - Add `Reroute` to a new `PASSTHROUGH_HELPER_CLASS_TYPES` set.
  - Add `PrimitiveBoolean`, `PrimitiveInt`, `PrimitiveFloat`, `PrimitiveString`,
    `PrimitiveStringMultiline`, `PrimitiveNode` to a new `VALUE_HELPER_CLASS_TYPES` set.
  - `HELPER_CLASS_TYPES` becomes the union of UI + broadcast + passthrough + value.
- Implement `resolve_helpers(nodes, edges) -> (nodes', edges', diagnostics)` in
  `helpers.py` (or a new `vibecomfy/porting/helper_resolve.py` if helpers.py grows
  beyond ~400 lines):
  - Topo-walk to a fixed point.
  - For each consumer edge whose source is a `GetNode`: resolve to matching
    `SetNode` by `name`, then follow `SetNode`'s upstream source. Emit a diagnostic
    if no matching `SetNode` exists (unresolved broadcast — already a diagnostic
    today; preserve that behavior).
  - For each consumer edge whose source is a `Reroute`: resolve to `Reroute`'s
    upstream source (transitively).
  - For each consumer edge whose source is a `Primitive*`: replace the edge with the
    primitive's literal `value` folded into the consumer's input kwargs; if the
    primitive node has a name label (or feeds through a named `GetNode`), register a
    `PublicInput` instead so the symbol survives at the decorator-shape top.
- Wire `resolve_helpers` into the conversion pipeline (call site is wherever
  `helper_stripped_nodes` is invoked today — find via `grep -rn helper_stripped_nodes
  vibecomfy/`). Strip happens AFTER resolution, never before — the resolver needs the
  helper nodes present to follow their edges.
- Remove `SetNode`, `GetNode`, `Reroute`, `PrimitiveNode` from
  `emitter.py:122-130 FALLBACK_CLASS_TYPES`. Add a defensive assertion that none of
  these class_types reach the emitter; raise `ConversionParityError` if one does
  (it would indicate the resolver missed a case).
- Update `port check` (and `--strict-ready-template`):
  - Demote helper-presence-in-source from warning to "expected — will be stripped".
  - Add a strict-ready hard-error code for helper-presence-in-emitted-output.
- Update `port lint` rules to flag `raw_call('GetNode'|'SetNode'|'Reroute'|'Primitive*'` in
  emitted Python.
- Regenerate every ready template under `ready_templates/` via the canonical command
  (`python -m vibecomfy.cli port convert <source> --ready-id <kind>/<name> --out
  ready_templates/<kind>/<name>.py`). Commit the regenerated files together with the
  resolver change so reviewers can see the before/after.
- Refresh `template_index.json` via `python -m tools.refresh_template_index` after
  regen.
- Add focused tests:
  - `tests/test_helper_resolve.py` — unit tests for chains (Reroute→Reroute→GetNode),
    forks (one SetNode → many GetNodes), and primitive inlining (folded literal,
    registered PublicInput).
  - `tests/test_emitted_no_helpers.py` — corpus-wide grep test: zero
    `raw_call('GetNode'|'SetNode'|'Reroute'|'Primitive*'` in any `ready_templates/**/*.py`.
  - Strict-ready test extension — at least one regenerated runexx/wanvideo template
    passes `port check --strict-ready-template` after the change.

## Scope (OUT)

- Layout-engine, preserve-polish, m4-productionize (those are m2/m3/m4 in the same
  epic).
- New typed wrappers (Sweep 3 / PR #20 territory).
- Widget alias gap-fill (Sweep 2 / PR #19 territory).
- The brief-vs-diff systemic check for megaplan itself (track (b) in
  `docs/decorator_template_emitter_completion.md`; runs in the megaplan repo, not here).
- Any helper-elimination at the **UI/litegraph emit** direction (M1's renderer
  territory). This sprint is JSON→Python only; the editor JSON direction handles
  helpers separately.
- Recovering helper/UI nodes on roundtrip. The intentional asymmetry stays: helpers and
  primitives are stripped one-way and reconstructed (if at all) by a different pass.

## Open questions

- **Named Primitive without GetNode link.** When a Primitive has a `name=` label but
  no `SetNode`/`GetNode` chain, should the name become a PublicInput symbol
  (`PUBLIC_INPUTS = {'fps': PublicInput(default=24, ...)}`), or fold to literal? The
  brief's working answer is "PublicInput if the name is non-default and used by >0
  consumers; literal otherwise" — verify against current runexx templates and update
  if the convention disagrees.
- **Primitive feeding multiple consumers with different types.** A
  `PrimitiveInt(value=24)` feeding both an `INT` socket and a `FLOAT` socket (Comfy
  silently coerces) — should the resolver emit two literals or one PublicInput with two
  consumers? Working answer: one PublicInput; the IR's `register_input` already
  supports multi-target.
- **Reroute with unknown `_outputs=('',)`.** Several current `Reroute` raw_calls in
  runexx templates have an empty-string output type tuple (`_outputs=('',)`).
  Investigate: is this an `object_info` gap, a passthrough convention, or evidence the
  reroute is dangling? Resolver behavior on dangling reroutes: drop with a diagnostic,
  same as unresolved `GetNode` broadcast.
- **Schema confidence for primitives.** Primitives have well-known widget schemas;
  confirm they're in `WIDGET_SCHEMA` / `object_info` cache so the literal-folding has
  type-correct values, not strings-for-everything.

## Constraints

- Conversion stays offline by default. No new model HEAD checks, no new network
  calls.
- Zero changes to runtime, queue, or session code. This is conversion-time only.
- No `--no-verify` on commits. Pre-commit hooks must pass clean.
- Determinism: regenerating a template twice MUST produce byte-identical output.
- Performance: resolution must not push `port convert` past 2× current wall time on
  the largest workflow in `workflow_corpus/`.

## Done criteria

1. `grep -rn "raw_call('GetNode'\|raw_call('SetNode'\|raw_call('Reroute'\|raw_call('Primitive"
   ready_templates/` returns ZERO matches.
2. `pytest tests/test_helper_resolve.py tests/test_emitted_no_helpers.py
   tests/test_strict_ready_templates.py tests/test_cli.py -q` is green.
3. `python -m vibecomfy.cli port check ready_templates/video/runexx_talking_avatar.py
   --strict-ready-template --json` passes (the user's named example).
4. `python -m tools.refresh_template_index --check` passes after regeneration.
5. `python -m vibecomfy.cli port lint ready_templates/video/runexx_talking_avatar.py`
   reports no helper/primitive `raw_call` violations.
6. Roundtrip docs in `CLAUDE.md` updated under "Bidirectional roundtrip limitations"
   to include Primitives alongside helpers.
7. The regenerated `ready_templates/video/runexx_talking_avatar.py` block the user
   pasted is replaced with consumer-side literals / PublicInputs, with zero
   `raw_call` rows for the seven nodes above.

## Touchpoints

- `vibecomfy/porting/helpers.py` — extend helper sets, add resolver entry point.
- `vibecomfy/porting/helper_resolve.py` (NEW, if helpers.py grows past ~400 lines) —
  the topo-fixed-point resolver.
- `vibecomfy/porting/normalize.py` — call resolver in the conversion pipeline.
- `vibecomfy/porting/emitter.py` — remove helper classes from `FALLBACK_CLASS_TYPES`,
  add defensive `ConversionParityError` assertion.
- `vibecomfy/porting/port_check.py` (or wherever port-check lives) — strict-ready
  hard-error code for helper-in-output.
- `vibecomfy/porting/lint.py` — lint rule for helper raw_call in emitted Python.
- `ready_templates/**/*.py` — regeneration (mechanical bulk update).
- `template_index.json` — refresh.
- `tests/test_helper_resolve.py` — NEW.
- `tests/test_emitted_no_helpers.py` — NEW.
- `CLAUDE.md` — roundtrip docs update.

## Anti-scope (don't touch)

- The verb-native router (`vibecomfy/router_rules.py`).
- Any `recipes/` files.
- The decorator emitter shape itself (`@ready_template`, `PublicInput`,
  ContextVar). That landed in Phase 3.5 v5 and is correct.
- The `vibecomfy/blocks/` and `vibecomfy/patches/` Layer 2 surface.
- RunPod harness, runtime/session, embedded ComfyUI integration.
- Custom-node pack pinning (`vibecomfy/node_packs.py`, `custom_nodes.lock`).
- The five PRs currently in flight (#18 m1-renderer-gate, #19 widget gap-fill,
  #20 wrapper codegen, megaplan #52). Block A is the next sprint AFTER those land.

## Megaplan profile recommendation

- **Tier**: `partnered` — premium reasoning end-to-end (plan/critique/revise/review),
  DeepSeek for the mechanical phases. The work has cross-cutting graph-rewrite
  judgment but the per-call code is mechanical. `directed` is too thin (resolver
  correctness needs adversarial critique); `premium` overspends on what's a
  conversion-time transform with clear evidence.
- **Robustness**: `full` — the default. Critique catches resolver edge cases
  (chains, forks, dangling reroutes) before they ship to the regenerated corpus.
- **Depth**: planner `medium`, critic `low`. Resolver has real judgment calls
  (named-primitive policy, dangling-reroute behavior); critic doesn't need to go
  deeper than `low` to flag missed cases.
- **Prep**: ON (`--with-prep`). The resolver touches normalization, emitter,
  port-check, lint, and the entire ready-template corpus — the planner needs to
  read the current code paths before committing to a plan.
- **Subagent venue**: launch the megaplan inside a subagent (`subagent-launcher`)
  to keep the main thread thin while the harness handles its own phase chatter.

## Done-when, in one sentence

When the user's pasted block from `ready_templates/video/runexx_talking_avatar.py`
no longer contains a single `raw_call('GetNode'|'SetNode'|'Reroute'|'Primitive*')`
line, every other regenerated ready template is the same, and strict-ready hard-errors
on any regression.
