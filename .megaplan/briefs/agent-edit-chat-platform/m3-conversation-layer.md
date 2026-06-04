# M3 — Conversation slice & memory (slim v1)

Publishes `agent-edit-contracts.md` §5 (a LIGHTWEIGHT Conversation/Message view).
Consumes M2's §3/§4 (a `Message` wraps a `TurnOutcome`).

> SCOPE DECISION (2026-06-04): v1 deliberately does the SIMPLE thing — show the
> **last 5 messages** in the panel and a **link to the session's JSON file** for full
> detail; give the agent the **last 5 messages** as context. The durable record is
> the existing on-disk turn store; we do not build history browsing, cross-conversation
> memory, search, per-workflow UUID keying, or multi-tab ownership in v1. Those are
> filed as future-work tickets (`agent-edit: full conversation history…` and
> `agent-edit: per-workflow keying + multi-tab…`). This shrinks M3 substantially — it
> is now a candidate to MERGE (its small backend bits into M2, its display bits into
> M4); keep it separate only if that's cleaner at chain-finalization.

## Outcome
The panel shows the **last 5 messages** of the current conversation as chat bubbles,
plus a small **"session: <path>"** affordance linking to the on-disk JSON for full
detail. The conversation survives a page refresh (minimal). The agent is given the
**last 5 messages** as context so follow-ups continue. ＋ New conversation starts
fresh. Reviewer checks: last-5 render; refresh keeps them; "now make it 30" after
"set it to 28" continues; the session-file link points at the right turn dir; New
resets.

## Scope — IN (small)
1. **§5 lightweight Conversation/Message view.** Just enough to (a) render the last 5
   messages and (b) thread the last 5 to the agent. `Message{role, text, turn_id?,
   outcome?}`; `role:"agent"` wraps a §3 `TurnOutcome`. No history/index/keying layer.
2. **Last-5 display.** Render the last 5 user/agent messages as bubbles in the thread.
3. **Session-file affordance.** A small "session: out/editor_sessions/<id>/" link/path
   in the panel (header or footer) so a user can open the JSON for full detail.
4. **Minimal persistence across refresh.** Store the active `session_id` in
   localStorage (one pointer, global — NOT per-workflow in v1). On load, rehydrate the
   last 5 from that session's turn store. Requires: make `response.json` unconditional
   (~3-line fix, validated) + a small derived `chat.json` per turn as the read unit.
5. **Agent memory = last 5 messages.** Thread the last 5 turns (user request + agent
   reply, and the per-turn applied `changes` if cheap) into `build_batch_messages`.
   Pure recency — NO relevance retrieval, NO cross-conversation (those are future).
6. **＋ New conversation** = fresh `session_id` + re-baseline (via M1's authority) +
   update the localStorage pointer. Old sessions stay on disk (never deleted).

## Scope — OUT (deferred to tickets)
History browser/dropdown, `index.json` manifest, load-past vs continue-from-canvas,
cross-conversation agent memory, search over prior turns/actions, relevance/"smart"
memory, per-workflow UUID keying (+ the `graph.extra` probe), multi-tab ownership.
(Single active session_id is global in v1; M1's per-canvas CAS prevents wrong-graph
applies, so a global pointer is safe — the only cost is the panel may show a different
graph's last-5 after a tab switch, acceptable for v1.)

## Locked decisions
- Server disk (`editor_sessions`) = source of truth; localStorage = ONE pointer
  (active `session_id`).
- Memory is the last 5 messages, recency only.
- No per-workflow keying in v1 (single global active session) — deferred.

## Open questions (planner resolves)
- Whether the last-5 user-message text is best read from `request.json` (`task`) or
  also materialized into `chat.json`; pick one read path.
- Whether to also write `chat.json` on accept/reject turns (for the file affordance)
  or only on submit.

## Constraints
- No regression in M1/M2 contracts.
- `pytest tests/test_comfy_nodes_agent_*.py` green; add tests for last-5 rehydrate and
  the unconditional `response.json`.

## Done criteria
- Last-5 messages render; refresh rehydrates them; the agent continues using the
  last-5; the session-file link resolves to the correct turn dir; New conversation
  resets the thread + re-baselines.

## Touchpoints
- `agent_edit.py` (make `response.json` unconditional; small derived `chat.json`),
  `agent_provider.py` (thread last-5 into `build_batch_messages`),
  `web/vibecomfy_roundtrip.js` (last-5 render; localStorage active session_id;
  rehydrate; the session-file link; New conversation), tests.

## Anti-scope
- No history browsing, index manifest, per-workflow keying, cross-conversation memory,
  search, or multi-tab ownership (all ticketed). Don't touch M1's baseline authority
  or M2's protocol/envelope except to consume them.

## Sizing note
Much smaller than originally scoped — likely well under a sprint. Profile can drop to
`directed/full/medium` @codex (the design is fully resolved and the work is mostly
additive display + a tiny persistence pointer + last-5 threading), OR fold into M2
(backend bits) + M4 (display bits). Decide at chain-finalization.
