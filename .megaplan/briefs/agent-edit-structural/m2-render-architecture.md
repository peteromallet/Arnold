# M2 — Scoped render architecture + message polish (agent-edit panel)

## Outcome
The agent-edit panel renders incrementally — each state transition updates only the DOM
sections it affects, the chat thread is virtualized/windowed, and render cost no longer
grows with session length — eliminating the residual review-phase sluggishness and the
recurring scroll/clip regressions. Plus the message-polish tail: link rewires verbalized
naturally, null old-values repaired, and a final aesthetic tidy.

## Context (why)
The panel currently rebuilds its ENTIRE DOM on every state change (renderAgentPanel →
renderHistory + renderSettings + renderDeveloper + every bubble + every collapsed details
pane). Live findings: the same turn-progress timeline is rendered duplicated under every
bubble; details JSON is prebuilt per render; long sessions get slower forever; the 2A
width-constraint change broke chat scrolling precisely because the layout is rebuilt
wholesale and fragile. Round 2A added rAF debouncing and lazy details — symptomatic relief;
the architecture is still rebuild-the-world. M1 (predecessor milestone) delivered
docs/agent-edit-client-lifecycle.md — an explicit transition table. Rendering becomes a
function of those transitions.

## Scope (IN)
1. **Scoped rendering**: split the panel into render sections (header/status strip, thread,
   composer+actions, notice block, settings popover, developer/diagnostics). Each lifecycle
   transition (per the M1 contract table) declares which sections it dirties; only dirty
   sections re-render. Keep the M1 transition layer as the sole render trigger.
2. **Thread incrementalism**: new chat messages APPEND a bubble node; existing bubbles are
   not rebuilt. Turn-status changes update that turn's bubble in place. The per-bubble
   details pane renders its content lazily on first expand (2A started this — finish it),
   and the turn-progress timeline renders ONCE per turn (kill the duplicated-under-every-
   bubble rendering observed live).
3. **Thread windowing**: render at most the most recent N bubbles (N≈30) with an
   "earlier messages" affordance that renders older ones on demand. Auto-scroll-to-newest
   on append unless the user has scrolled up (preserve their position). This must finally
   make scroll behavior boring and reliable.
4. **Overlay draw-model integration**: the 2A overlay cache keyed by candidateGraphHash +
   graph revision stays; wire its invalidation into the M1 transition layer (apply/reject/
   undo/new-conversation invalidate it) instead of ad-hoc call sites.
5. **Message polish (backend)**:
   a. Link-rewire humanization: changes to LINK-type fields currently verbalize raw
      endpoint dicts ("Updated SaveImage images from "{'scope_path': '', 'uid': '18'...").
      Verbalize as "rewired <NodeTitle> <input> to come from <SourceTitle> <output>".
   b. Null old-values: the FieldChange old-value repair skips null olds ("denoise from
      null to 0.4", "filename_prefix from null to fox/raw" — both had real old values).
      Repair null olds from the submitted UI graph the same way non-null wrong olds are
      repaired; when the field genuinely had no prior value, say "set X to Y" instead of
      "from null".
6. **Aesthetic tidy** (small, bounded): consistent spacing/typography in the thread,
   details panes never overflow the panel, candidate chips/badges aligned, status strip
   wording consistent. No redesign — tighten what exists.

## Scope (OUT)
- No framework adoption (no React/lit/etc), no build step.
- No backend protocol/session-format changes (5a/5b are message-synthesis only).
- No new features (no history browser, no multi-tab support, no queue changes).
- No changes to docs/agent-edit-contracts.md §1–§8 semantics.

## Locked decisions
- Vanilla JS + manual DOM. Scoped rendering = explicit section render functions + a
  dirty-set, driven from the M1 transition layer. No virtual DOM.
- The M1 lifecycle contract (docs/agent-edit-client-lifecycle.md) is authoritative input;
  if rendering needs a transition the table lacks, extend the table + its tests in the
  same change (contract stays in lockstep).
- Behavior baseline = the live-validated matrix on the M1 milestone head; this milestone is
  behavior-preserving for everything except message wording (5a/5b) and the windowing
  affordance.
- Keep the existing visual language (colors, layout, components) — polish, don't redesign.

## Open questions (planner must resolve)
- Section boundaries: exact split of composer vs notice vs actions (resolve from current
  DOM structure; bias to fewer, larger sections if dirty-tracking gets fiddly).
- Windowing N and the "earlier messages" UX (button vs scroll-triggered) — pick simplest
  reliable (button is fine).
- Whether settings/developer sections render lazily on first open (probably yes — they're
  rarely opened).

## Constraints
- Gates green at every commit: node smoke (0 fail) + pytest agent tests (exit 0); never
  touch tests/known_failures.txt.
- Perf acceptance: with a 50-message session and a 12-node candidate overlay active,
  interaction must stay smooth — add a smoke-level guard asserting appending a message
  does NOT re-render existing bubbles (call-count instrumentation), and that a state
  transition dirtying only the composer does not rebuild the thread.
- The scroll behavior must be covered by tests: append → scrolled to newest; user scrolled
  up → position preserved; reload → scrolled to newest.

## Done criteria
- Append-only thread rendering verified by tests; duplicated per-bubble timeline gone.
- Windowing works (>N messages → older ones behind the affordance).
- Scroll reliable per the three test cases above.
- Link rewires + null-olds verbalize naturally (pytest-asserted on rendered message text).
- Smoke + pytest green; live matrix spot-check clean.

## Touchpoints
- vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js (render layer rework)
- vibecomfy/comfy_nodes/web/comfy_adapter.js (overlay invalidation hooks only)
- vibecomfy/comfy_nodes/agent_edit.py (message synthesis 5a/5b)
- docs/agent-edit-client-lifecycle.md (extend table if needed)
- tests/browser/roundtrip_smoke.test.mjs, tests/test_comfy_nodes_agent_*.py

## Anti-scope
- Do not touch ready_templates/, workflow_corpus/, the CLI, megaplan engine code, or the
  ComfyUI checkout. Do not modify out/editor_sessions evidence. Do not "clean up" parts of
  vibecomfy_roundtrip.js unrelated to rendering/messages.
