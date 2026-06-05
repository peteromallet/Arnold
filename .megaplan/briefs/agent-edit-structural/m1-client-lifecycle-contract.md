# M1 — Client lifecycle contract + state authority (agent-edit panel)

## Outcome
A written, tested client-side lifecycle contract for the VibeComfy agent-edit panel: an
explicit state machine (states, transitions, and each transition's re-sync obligations)
implemented as a small state store that the panel consumes — replacing today's implicit,
leak-prone ad-hoc state mutations. Published as `docs/agent-edit-client-lifecycle.md`
(the artifact M2 builds on) plus the implemented store + transition tests.

## Context (why)
Live validation of the m0–m4 chat epic (merged: PRs #50,#51,#54,#55,#56; plus live-fix
commits a23c400, 83ad22a, 2db611e on main) found that every client-side bug lived at a
TRANSITION SEAM: undo didn't rebaseline the backend; reload dropped the pending candidate;
late async responses polluted fresh sessions; hand-edits slipped past; queue-guard context
went stale; post-reject candidates stayed applyable. Each was fixed point-wise (rounds 1,
2A, 2B) — but the class keeps reappearing because the client's lifecycle was never spec'd.
The backend has a clean CAS baseline authority (docs/agent-edit-contracts.md §1); the
client needs its mirror image.

## Scope (IN)
1. **Lifecycle contract doc** `docs/agent-edit-client-lifecycle.md`: enumerate client
   states (IDLE, SUBMITTING, CLARIFY, AWAITING_REVIEW, APPLYING, ERROR(+recovery), plus
   panel-closed/reopened and page-reload entry) and EVERY transition with its re-sync
   obligations (what must be invalidated, what must be POSTed to the backend, what must be
   re-fetched, what renders). Cover: submit, response(ok/clarify/edit+clarify/failure),
   apply, reject, undo (panel-initiated rebaseline), stop/abort, new-conversation, page
   reload/rehydrate (incl. pending-candidate restore via /chat latest_candidate),
   hand-edit detection, superseded-candidate invalidation, submit-epoch rules for late
   async responses.
2. **State store implementation**: consolidate panel.state mutations behind a small typed
   transition layer (plain JS module in vibecomfy/comfy_nodes/web/, no framework) so every
   transition goes through one function with its obligations enforced. The existing
   round-2B epoch counter, rebaseline-on-undo, rehydrate-restore and queue-guard logic must
   be RELOCATED into this layer, not duplicated.
3. **Transition tests**: jsdom smoke tests exercising each contract edge (the file
   tests/browser/roundtrip_smoke.test.mjs already covers many point-wise — reorganize/extend
   to cover the table exhaustively; keep all existing tests passing).
4. **Projection authority cleanup**: round 2B already stopped the client structural hash
   from blocking Apply; finish the job — remove the now-dead client structural-projection
   code paths (keep the full-graph hash the backend ingest needs), and add a golden
   cross-test asserting the client-submitted hash matches the backend's recomputation for
   a fixture graph (backend CAS stays the single authority).
5. **Wire-context contract formalization**: round 2B implemented per-iteration node index +
   re-render-after-no-edit-iterations + previous-prose in agent_provider.py. Write the
   rule down as a short section in docs/agent-edit-contracts.md (§8 "Iteration context
   contract") and add the missing pytest edges (multi-search runs, budget exhaustion mid-
   iteration, index correctness after node add/remove within a turn).

## Scope (OUT — M2's job or not ours)
- NO render-architecture changes (no dirty-bit rendering, no virtualization) — M2.
- NO visual redesign, no CSS overhaul beyond what state-store relocation strictly needs.
- NO wire-protocol semantic changes beyond documenting what 2B shipped.
- NO backend session/state-file format changes.

## Locked decisions
- Vanilla JS, no framework, no build step — the web extension stays dependency-free.
- Backend CAS is the single graph authority (contracts §1); client never blocks on its own
  structural hash.
- The §1–§7 contracts in docs/agent-edit-contracts.md are authoritative and unchanged
  (we ADD §8 and the client-lifecycle doc; we do not relitigate existing sections).
- Panel behavior as currently live-validated (10/10 matrix scenarios on commit 2db611e) is
  the behavioral baseline — this milestone is behavior-preserving except where the contract
  table reveals an unhandled edge (then: implement the contract's answer, with a test).
- State store shape: a module-level `transition(panel, event, payload)` dispatcher with one
  named handler per transition is sufficient; do not introduce classes/observables.

## Open questions (planner must resolve)
- Exact state/event taxonomy granularity (e.g. is APPLYING a state or a flag on
  AWAITING_REVIEW?) — resolve from the existing PANEL_STATE enum + live behavior; do not
  invent states with no behavioral difference.
- Where hand-edit detection hooks in (canvas change listener vs submit-time compare) —
  today it is submit-time (backend ingest detects); keep that unless the contract table
  shows a cheap improvement.
- How much of renderAgentPanel's implicit state-reading should move behind store getters
  now vs in M2 — bias to minimal here; M2 owns rendering.

## Constraints
- Gates that must stay green at every commit: `node --test tests/browser/roundtrip_smoke.test.mjs`
  (0 fail) and `PYENV_VERSION=3.11.11 python -m pytest tests/test_comfy_nodes_agent_*.py -q
  -p no:cacheprovider` (exit 0). NEVER touch tests/known_failures.txt.
- No regression to the live-validated matrix behaviors (the smoke suite encodes most; the
  reviewer should check the contract table against the suite for gaps).
- Keep vibecomfy_roundtrip.js diff reviewable: state-store extraction may move code, but
  avoid gratuitous reformatting.

## Done criteria
- docs/agent-edit-client-lifecycle.md exists with the full transition table; every row
  names its re-sync obligations and its covering test.
- All panel state mutations for the covered transitions flow through the transition layer.
- Smoke suite green with new transition tests; pytest green incl. §8 context tests.
- Dead client structural-projection code removed; golden hash cross-test passes.

## Touchpoints
- vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js (state extraction)
- vibecomfy/comfy_nodes/web/comfy_adapter.js (only if guard install hooks need relocation)
- vibecomfy/comfy_nodes/agent_provider.py + agent_edit.py (§8 doc + tests only)
- docs/agent-edit-client-lifecycle.md (new), docs/agent-edit-contracts.md (§8 added)
- tests/browser/roundtrip_smoke.test.mjs, tests/test_comfy_nodes_agent_*.py

## Anti-scope
- Do not touch ready_templates/, workflow_corpus/, vibecomfy/porting/, the CLI, or any
  megaplan engine code. Do not modify out/editor_sessions evidence. Do not change the
  ComfyUI checkout. Do not refactor agent_session.py beyond what §8 tests need.
