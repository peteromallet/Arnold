# M1 — Edit-state authority & apply-eligibility

Publishes `agent-edit-contracts.md` §1 (edit-state/baseline authority) and §2
(apply-eligibility). The never-wedge foundation everything else builds on.

## Outcome
The agent-edit session never strands the user in an unrecoverable
`StaleStateMismatch`: every baseline transition (accept, undo, rebaseline,
continue-from-canvas) goes through ONE CAS-guarded authority, and "can I apply this
candidate now, and if not why" is one predicate. Reviewer checks: Apply→Undo→edit→
Apply works; a state divergence offers one-click recovery, not a dead end.

## Scope — IN
1. **One edit-state/baseline authority (§1).** Consolidate every write to
   `baseline_graph_hash` behind a single owner; no code outside it mutates baseline.
   All transitions CAS-guarded (succeed only if the session baseline still equals the
   caller's last-known baseline) + audited.
2. **`/vibecomfy/agent-edit/rebaseline` endpoint** — the authority's public entry:
   carries current client graph + last-known baseline; updates only on CAS match;
   writes a `rebaseline` audit event.
3. **Undo awaits re-baseline** — `undoLastApply` calls the authority (to the restored
   pre-apply graph) and re-enables submit only on success.
4. **Explicit recovery, never silent heal** — on an ingest mismatch, surface a
   one-click "re-baseline to current canvas" (explicit, audited); ingest never
   silently accepts any prior hash.
5. **Apply-eligibility predicate (§2)** `eligibility(candidate, liveCanvas) ->
   {applyable, reason}` encoding latest-only / superseded / queue-blocked /
   stale-canvas. Replaces the scattered `canvas_apply_allowed` + token + "latest
   turn?" checks. Published for the UI (M4) to consume.

## Locked decisions
- Re-baseline = backend CAS endpoint, NOT client `session_id` re-seed (re-seed dodges
  ingest via "no baseline ⇒ pass" but destroys history/idempotency/audit).
- Reason in server-computed structural hashes; `live_canvas_token` stays a
  client-side apply-race guard only — do not conflate.
- Keep the op-based faithful-apply engine and v2 gates unchanged.
- **The CAS check sits AFTER the idempotency-replay block** in `_mutate_turn_state`
  (`agent_session.py:~623`): a legitimate network-retry must replay the cached
  authoritative response (which already carries the post-accept baseline), NOT get
  CAS-rejected. (Validated: replay today returns a cached response with no baseline
  check; accept advances `baseline_graph_hash` with no CAS pre-check — `:811`. CAS is
  net-new, not a double-guard.)

## Open questions (planner resolves)
- Exact rebaseline wire shape and how the client tracks "last-known baseline" for CAS.
- Whether the authority is a new module or a consolidation inside `agent_session.py`.
- Interaction of CAS with the existing idempotency-key machinery (validate they
  compose, don't double-guard).

## Constraints
- No regression in merged preview-fidelity / turn-progress behavior.
- `pytest tests/test_comfy_nodes_agent_*.py` green (modulo the 2 known baseline
  failures); browser smoke green.

## Done criteria
- Apply → Undo → new edit → Apply: no dead-end `StaleStateMismatch` (headless + live).
- State divergence → one-click recovery → resubmit succeeds (audited rebaseline).
- `eligibility()` drives Apply enable/disable with a human reason; it is the ONLY
  place that answers "can I apply this candidate."
- §1, §2 are real, imported, tested interfaces M2/M4 can build on.

## Touchpoints
- `agent_session.py` (baseline lifecycle: `accept_turn`, candidate record, structural
  hash; the new authority + CAS + audit), `agent_edit.py` (`_stage_ingest_v2`, submit
  plumbing, recovery surfacing), `agent_gates.py` (`state_match_ok` compare — read for
  the CAS contract; don't weaken silently), `web/vibecomfy_roundtrip.js`
  (`undoLastApply`, `applyAgentCandidate`, eligibility consumption), tests.

## Anti-scope
- Don't touch the conversation/message model (M3), the UI rebuild (M4), the protocol
  collapse or typed envelope (M2). Don't change hashing algorithms or projection
  semantics unless a test proves the hash contract is wrong.

## Topological note
This reshapes a cross-module contract (who owns baseline, across
session/edit/gates/JS) → premium planner; a bad authority topology breaks
non-locally. Profile: `partnered/full/high` @codex, no prep.
