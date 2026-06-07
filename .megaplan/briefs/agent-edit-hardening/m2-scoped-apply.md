# m2 — Scoped apply: delta-region validation instead of whole-graph hash equality

## Outcome
Applying a candidate validates only the region the edit actually touches, so unrelated canvas
activity (tab switches, reloads, saves, edits to other nodes) can no longer invalidate a
pending candidate. When the touched region itself drifted, the user gets the existing one-click
rebaseline+resubmit recovery. Apply ends with a verified-on-canvas confirmation.

## Why (evidence from live testing, 2026-06)
Accept currently requires the live canvas hash to equal the submit-time hash. In real use this
is so brittle that "Apply doesn't work" was reported as a bug: a 3-field KSampler candidate was
refused (`StaleStateMismatch`, stage accept) because the user had switched workflow tabs —
nothing the candidate touched had changed. Every page reload (ComfyUI discards unsaved canvas
state) and every unrelated hand-edit kills every pending candidate. The strict check protects
against clobbering, but at whole-graph granularity it blocks the common safe case.

## Scope (IN)
1. **Server accept path (vibecomfy/comfy_nodes/agent_edit.py):** replace whole-graph hash
   equality with touched-region validation:
   - Touched region := the set of node uids referenced by the turn's delta ops (field edits,
     link rewires, adds, removes), resolved via the existing uid/id alias map.
   - Field edits: the live canvas node's current value for each edited field must equal the
     candidate's recorded OLD value (the baseline value the delta was computed against).
   - Link rewires: the live input's current source endpoint must match the recorded old endpoint.
   - Removes: the node must still exist (already-gone = treat as satisfied, not conflict).
   - Adds: the candidate's new uids must not collide with live uids.
   - Nodes NOT in the touched region are ignored entirely — position, collapse, unrelated
     widgets, unrelated wiring, even added/removed unrelated nodes do not block accept.
2. **Application:** apply the delta ops onto the LIVE canvas graph (not a wholesale replace
   with the candidate snapshot) so untouched user state survives. The in-place configure path
   already exists for accept — rework it to merge scoped changes.
3. **Conflict response:** when touched-region validation fails, return the m1 contract error
   with `rebaseline_recovery` so the client's existing Rebaseline & retry button regenerates
   the candidate against the current canvas. The error message names WHICH field/node
   conflicted, humanized ("KSampler steps changed on the canvas since this candidate was
   created (now 25, expected 20)").
4. **Post-apply verification:** after applying, re-read the touched nodes from the live graph
   and confirm every new value/endpoint landed; the success response reports it and the panel
   message reads e.g. "Applied — 3 changes verified on canvas." A verification miss is an error
   bubble, never a silent assumption.
5. **Contract doc:** extend docs/agent-edit-response-contract.md (from m1) with the scoped
   accept request/response semantics, the touched-region definition, and the conflict payload.

## Locked decisions
- The candidate continues to ship the full preview graph (the canvas overlay needs it);
  ONLY accept validation and application become delta-scoped.
- The old whole-graph hash comparison is kept as a non-blocking diagnostic in the response
  details (useful forensics), never as a gate.
- Recovery UX is the existing rebaseline+resubmit flow — no new modal/affordance.
- Turn artifacts under out/editor_sessions/ keep recording exactly as today (before.py /
  after.py / audit) — the oracle workflow must keep working.

## Open questions for the planner
- Where the per-op old values live today (response change_details operations vs the turn's
  before.py/baseline graph) and which is authoritative for the conflict comparison — pick one,
  document it in the contract doc.
- Whether queue gating (Gate B / queue_allowed) needs recomputation after a scoped apply onto
  a drifted-but-compatible canvas (likely yes for the queue path only — keep Apply unblocked).

## Constraints
- All suites green (counts at fork: 111 smoke / 87 lifecycle / 338 pytest), plus new scoped-
  accept tests. Update tests that encoded strict-hash refusal to the new contract — but KEEP a
  test proving a genuine touched-region conflict still refuses.
- The live matrix behaviors must hold; in particular: hand-edit to an UNRELATED node then
  Apply → succeeds; hand-edit to a TOUCHED field then Apply → humanized conflict + recovery
  button; reload (canvas revert) then Apply where the touched region reverted → conflict +
  recovery works end-to-end.
- DeepSeek-generated deltas sometimes re-emit identical ops (old == new); identical ops are
  no-ops for validation (never conflict on a field whose old == new).

## Done criteria
- A candidate created, followed by edits to OTHER nodes (move/value/add), applies cleanly.
- A candidate whose touched field drifted refuses with the named conflict + working one-click
  recovery (test drives the full rebaseline→resubmit→AWAITING_REVIEW sequence).
- Apply success responses carry verification results; panel shows "verified" phrasing.
- Contract doc extended; pytest covers the validation matrix (field/link/add/remove ×
  clean/drifted), browser tests cover the panel flows.

## Touchpoints
vibecomfy/comfy_nodes/agent_edit.py (accept/validation/application),
vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js + agent_edit_lifecycle.js (recovery flow,
verified messaging), tests/test_comfy_nodes_agent_edit.py, tests/browser/roundtrip_smoke.test.mjs,
docs/agent-edit-response-contract.md.

## Anti-scope
- Do NOT change the model/provider side (delta generation, prompts, projection) — this is
  accept-time semantics only.
- Do NOT split files or move module state (m3).
- Do NOT touch ready_templates/, workflow_corpus/, vibecomfy IR/CLI/router.
- Do NOT modify out/editor_sessions evidence directories.
- No new UI surfaces beyond the existing failure card/bubble + recovery button.
