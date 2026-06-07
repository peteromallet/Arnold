# m1 — Typed response contract & single payload boundary

## Outcome
Every agent-edit server response carries a mandatory discriminated `outcome.kind`; the client
classifies by switching on it (zero field-sniffing), and all server payloads cross exactly one
normalization boundary. Submit and accept failure surfaces become symmetric. Published as
`docs/agent-edit-response-contract.md` — the handoff artifact m2 consumes.

## Why (evidence from live testing, 2026-06)
Response classification by duck-typing broke four separate times in production-style testing:
- no-op turns verbalized as edits and entering review (fix round 13),
- the live submit path missing the noop classifier because the artifact omitted
  `candidate: null` (round 17),
- candidate-field sniffing winning over `outcome.kind: "noop"` because real noop responses DO
  carry candidate/graph/hash fields (round 18),
- `/chat latest_candidate` restoring a noop turn and dragging an IDLE panel back into review
  (round 19, commit 3d12eb2).
Separately, the stale-canvas Rebaseline & retry button silently never rendered because backend
errors carry snake_case `rebaseline_recovery` while the client synced only camelCase (round 13,
commit 1064e97) — and the accept stage never got the recovery wiring the submit stage has
(see commit history after 12386b5 for the tactical accept-stage patch this milestone formalizes).

## Scope (IN)
1. **Server (vibecomfy/comfy_nodes/agent_edit.py, routes.py):** every response from submit,
   accept, rebaseline, and the /chat endpoint (including each `latest_candidate` and each
   rehydrated message's turn record) carries `outcome: {kind, ...}` with
   `kind ∈ {"candidate", "noop", "clarify", "error"}`. Existing fields stay (back-compat) but
   `kind` is authoritative and validated server-side before send.
2. **Client boundary module:** one fetch-layer normalization site (new small module or a
   clearly-bounded section of the panel code) that (a) converts snake_case payload fields the
   client consumes to their camelCase names exactly once, (b) normalizes `rebaseline_recovery`
   from top-level and nested-issue positions, (c) stamps `outcome.kind` onto LEGACY payloads
   (pre-contract stored sessions rehydrated from disk) using the current inference rules —
   this adapter is the ONLY place inference logic survives; delete every other sniffing site
   (candidateGraphFromResult noop checks, graph_unchanged+gates inference at the submit path,
   the latest_candidate noop guard) in favor of switching on the stamped kind.
3. **Classification:** lifecycle dispatch (`NOOP_RESPONSE`, `OK_CANDIDATE_RESPONSE`,
   `CLARIFY_ONLY_RESPONSE`, failure events) selected by `outcome.kind` switch only.
4. **Symmetric failure surface:** accept-stage failures carry `rebaseline_recovery` exactly
   like submit-stage; both stages render the failure as a conversation bubble (single-surface
   rule) and both offer the one-click "Rebaseline & retry" (rebaseline to current canvas +
   resubmit the original task). If a tactical accept-recovery patch already landed on main,
   absorb/normalize it into the contract rather than duplicating.
5. **Contract doc:** `docs/agent-edit-response-contract.md` — every kind, its required and
   optional fields, the legacy-adapter rules, and the failure/recovery payload shape. m2 will
   extend this doc with scoped-accept semantics; write it to be extended.

## Locked decisions
- Union members: exactly `candidate | noop | clarify | error` (a clarify turn may also carry a
  candidate in future — represent that as kind=candidate with a `clarification` field, NOT a
  fifth kind).
- The legacy adapter lives client-side at the boundary (server does not rewrite stored session
  files on disk; editor_sessions artifacts are immutable evidence).
- snake_case is canonical on the wire; camelCase is canonical inside the client; conversion
  happens only at the boundary module.
- No bundler/build step: the boundary module is a plain JS file loaded like the existing ones.

## Open questions for the planner
- Whether `/chat` message records need `kind` per message or only per `latest_candidate` and
  per turn record (decide from how the thread renderer consumes them).
- Exact placement of the boundary module given ComfyUI web-extension loading (plain script /
  module imports) — follow whatever pattern vibecomfy_roundtrip.js + agent_edit_lifecycle.js
  already use to share symbols.

## Constraints
- All existing suites stay green: node --test tests/browser/roundtrip_smoke.test.mjs (111),
  tests/browser/agent_edit_lifecycle.test.mjs (87), pytest tests/test_comfy_nodes_agent_*.py (338).
  Update tests whose fixtures lack `outcome.kind` by adding it (the contract makes it mandatory)
  — but keep dedicated legacy-shape tests exercising the adapter.
- The 10-scenario live matrix behaviors (chat, clarify-as-bubble, undo, reject, reload-restore,
  rebaseline recovery, noop-stays-IDLE) must not regress — they are encoded in the suites.
- Respect docs/agent-edit-client-lifecycle.md; extend it where transitions change.

## Done criteria
- `grep` finds no response-shape inference outside the boundary module (no
  `graph_unchanged`-based classification, no candidate-field sniffing in lifecycle/renderers).
- New tests: per-kind classification table tests; legacy payload (no outcome field) classified
  via adapter; accept-stage stale failure → recovery button → rebaseline+resubmit transition;
  failure bubble rendered in-thread for both stages.
- docs/agent-edit-response-contract.md exists and matches the implementation.

## Touchpoints
vibecomfy/comfy_nodes/agent_edit.py, vibecomfy/comfy_nodes/routes.py,
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js, vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js,
tests/browser/*, tests/test_comfy_nodes_agent_edit.py, docs/agent-edit-response-contract.md,
docs/agent-edit-client-lifecycle.md.

## Anti-scope
- Do NOT change accept validation semantics (that is m2).
- Do NOT split files or move module-level state (that is m3).
- Do NOT touch ready_templates/, workflow_corpus/, the vibecomfy IR/CLI/router, or anything
  outside the agent-edit panel surface.
- Do NOT modify out/editor_sessions evidence directories.
- No visual redesign; message prose stays as shipped.
