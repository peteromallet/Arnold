# Megaplan brief — Agent-edit session/state robustness + conversational clarify

> Sense-checked by Codex (GPT-5.5) against the live source on 2026-06-04;
> verdict "sound with the listed changes." Corrections folded in below
> (notably: candidate generation does NOT advance the baseline — only `accept`
> does; these are distinct problems sharing one UX surface, not "one root").

## Outcome
The VibeComfy agent-edit session never strands the user in an unrecoverable
`StaleStateMismatch`, and a `clarify()` turn becomes a real multi-turn
**conversation** (ask → answer inline → continue with memory). A reviewer
checks: (a) Apply→Undo→edit→Apply works with no dead-end mismatch; (b) a clarify
question answered in the panel produces a landed edit on the next turn, using the
answer; (c) when state genuinely diverges, the UI offers one-click recovery, not
a dead end.

> SCOPE: this plan is the **foundation** the chat interface builds on. It is no
> longer just "fix the wedging bug" — it **establishes and publishes the
> execution-side contracts** in `agent-edit-contracts.md` (§1 edit-state/baseline
> authority, §2 apply-eligibility predicate, §3 typed TurnOutcome, §4 typed
> response envelope, §6 provider-readiness) AND hardens the turn loop (parser).
> The conversational UX + the Conversation/Message model (§5) live in the
> chat-interface megaplan (`agent-edit-chat-interface.md`), which CONSUMES these
> contracts. Publishing §1–§4/§6 as real, documented interfaces is a deliverable
> here — so MP2 builds on contracts, not by reopening these files.

## Framing: distinct problems sharing one UX surface (NOT one root)
These do **not** share a single root cause — Codex verified this against the
code. They share the **agent-edit UX surface and touchpoints**. This plan keeps
the two correctness workstreams (A, C); the conversational workstream (B) is now
owned by the chat-interface plan:

- **A. Session baseline / state protocol (prerequisite).** The server session
  baseline (`baseline_graph_hash`) only advances on `accept`
  (`agent_session.py:811`). `undoLastApply` (`roundtrip.js:4492`) reloads the
  prior client graph but makes **no backend call**, so after an apply+undo the
  live canvas (reverted) no longer matches the accepted baseline, and the next
  submit fails ingest (`agent_edit.py:693`, structural-hash compare in
  `agent_gates.py:80`). Submit deliberately does **not** send `baseline_turn_id`;
  the backend computes its own `submit_structural_graph_hash`
  (`agent_session.py:428`) and compares to the stored baseline.
- **B. Conversational clarify — MOVED to the chat-interface plan.** (The frontend
  already preserves `session_id` across CLARIFY at `roundtrip.js:4009`, but
  `build_batch_messages` cold-starts with no memory; that work now lives in the
  chat plan, which owns all conversational UX + memory.)
- **C. Turn-loop / parser hardening (independent).** `extract_batch_fence`
  (`agent_provider.py:133`) raises `MalformedModelJSON` on a missing ```batch
  fence; the bounded retry (`agent_provider.py:779`) recovers it but adds
  ~20-30s. This is provider/parser robustness, unrelated to A or B.

## Scope — IN (foundation + published contracts, then parser)

### Workstream A — Edit-state authority + re-baseline (`contracts.md` §1)
1. **One edit-state/baseline authority.** Consolidate every baseline transition
   (accept, undo, rebaseline, continue-from-canvas) behind a single owner; no code
   outside it writes `baseline_graph_hash`. All transitions **CAS-guarded** (only
   if the session baseline still equals the caller's last-known baseline) + audited.
2. **Backend re-baseline endpoint, CAS-style.** `/vibecomfy/agent-edit/rebaseline`:
   request carries the current client graph + last-known baseline; server computes
   the new structural hash and updates only on the CAS match. Writes a `rebaseline`
   audit event. (This is the authority's public entry point.)
3. **Undo awaits re-baseline.** `undoLastApply` calls the authority (to the restored
   pre-apply graph) and only re-enables submit once it succeeds.
4. **Pending-candidate replacement is state cleanup, not a baseline bug.** A new
   submit already marks prior candidates `unknown` (`agent_session.py:500`); ensure
   it leaves the baseline untouched and the client state clean.
5. **Explicit recovery, never silent auto-heal.** On an ingest mismatch, surface a
   one-click "re-baseline to current canvas" (explicit, audited) — never make
   ingest silently accept any prior hash (that forks history).

### Workstream B — Published contracts (`contracts.md` §2/§3/§4/§6)
6. **Apply-eligibility predicate (§2).** A single `eligibility(candidate, liveCanvas)
   -> {applyable, reason}` encoding latest-only / superseded / queue-blocked /
   stale-canvas. Replaces the scattered `canvas_apply_allowed` + token + "latest
   turn?" checks. The UI consumes it (Apply enabled/disabled + tooltip).
7. **Typed `TurnOutcome` (§3).** Make the turn result a tagged union
   (`edit | clarify | edit+clarify | failure | noop | budget`) — in particular
   stop treating `clarify()` as an early terminal *before* apply (`agent_edit.py:985`)
   so `edit+clarify` is representable. (MP2 builds the UX on this; MP1 makes it
   emittable + carried in the envelope.)
8. **Typed response envelope (§4) + always-non-empty `message`.** The envelope is a
   documented shape the UI reads as state: `message` (non-empty), `TurnOutcome`,
   candidate + `eligibility`, `audit_ref`; raw gate booleans/hashes become
   debug-only fields, not UI inputs. (The message *synthesizer* that guarantees
   non-empty is MP2's, but the envelope field + contract are fixed here.)
9. **Provider-readiness (§6).** One `readiness() -> {ready, reason}` the header dot,
   composer lock, and setup warning all read.

### Workstream C — Turn-loop / parser hardening
10. Cut the routine first-attempt missing-```batch-fence failure (prompt and/or
    make `extract_batch_fence` tolerant of a lone batch block / minor wrapping).
    Keep the bounded retry as a backstop; it should be the exception.

> Conversational clarify memory + the Conversation/Message model (`contracts.md`
> §5) are **MOVED** to the chat-interface megaplan, which consumes §1–§4/§6 above.

## Scope — OUT / anti-scope
- Do **not** rework the just-merged preview overlay or live turn-progress feed
  beyond wiring the inline-reply affordance into the existing feed.
- Do **not** change the faithful op-based apply engine, the gate set, or lowering.
- Do **not** change graph-projection **semantics** or hashing **algorithms**
  unless a test proves the hash contract itself is wrong. (Adding baseline-hash
  storage/exposure in frontend state and/or session records IS in scope —
  re-baseline needs it.)
- No new transport beyond the one small re-baseline endpoint; reuse `/ws` + the
  existing POST endpoints otherwise.

## Locked decisions
- **Re-baseline = backend CAS endpoint**, not client-side `session_id` re-seed
  (re-seed dodges ingest because "no baseline ⇒ pass" at `agent_gates.py:80`, but
  destroys turn history, clarify memory, idempotency, and audit continuity).
- Re-baseline and ingest reason in **server-computed structural hashes**; the
  frontend **live_canvas_token** stays a client-side apply-race guard only
  (`roundtrip.js:920`, `:4194`) — do not conflate the two.
- Keep the op-based faithful-apply engine and v2 gates; reuse the shipped
  `CLARIFY` state, `VC_COLORS`, `invalidateCandidateState`, and the Activity feed.
- Model route stays `deepseek-v4-pro` (deepseek route), `max_tokens=393216`.

## Open questions (planner resolves)
- Exact re-baseline wire shape (dedicated endpoint vs. a field on submit) and how
  the client tracks "last-known baseline hash" to send for the CAS check.
- Clarify memory shape: replay prior turns as chat messages vs. a compact
  "conversation so far" block injected into `build_batch_messages`.
- Whether undo must preserve an in-progress clarify conversation (couples B to A)
  or may reset it (keeps B independent).

## Constraints
- No regression in merged preview-fidelity / turn-progress behavior.
- `pytest tests/test_comfy_nodes_agent_*.py` green (modulo the 2 known baseline
  failures); browser smoke green.
- DeepSeek key stays in `~/.hermes/.env` (never committed).

## Done criteria
- Headless + live tests pass:
  - Apply → Undo → new edit → Apply (no dead-end `StaleStateMismatch`).
  - State divergence → one-click recovery → resubmit succeeds (explicit rebaseline,
    audited).
  - First-attempt malformed-batch retries near-zero on the SD3-class prompt.
  - **Contracts published & exercised:** `eligibility()` drives Apply enable/disable
    with a reason; a turn can emit `edit+clarify` (carried in the envelope); the
    envelope is typed with a non-empty `message` field; `readiness()` drives a
    single ready/blocked signal. `agent-edit-contracts.md` §1–§4/§6 are real,
    tested interfaces MP2 can import.
  - (Conversational memory / clarify-answer flow + the Conversation/Message model
    §5 are validated in the chat plan — this plan only proves the session can carry
    them without wedging, and publishes the contracts they build on.)
- A `StaleStateMismatch` is never a dead end in a normal flow.

## Touchpoints
- `agent_session.py` — baseline lifecycle (`accept_turn` ~811, candidate record
  ~560, new-submit `unknown` marking ~500, structural-hash compute ~428); add
  CAS re-baseline + audit event.
- `agent_edit.py` — `_stage_ingest_v2` (~685/693), submit/turn plumbing; recovery
  surfacing.
- `agent_gates.py` — `state_match_ok` baseline compare (~80) — read for the CAS
  contract; do not weaken silently.
- `agent_provider.py` — `build_batch_messages` (~163/265) conversation threading;
  `extract_batch_fence` (~133) + retry (~779) hardening.
- `vibecomfy_roundtrip.js` — `undoLastApply` (~4492), `applyAgentCandidate`
  (~4154), submit handler + CLARIFY branch (~3960), `invalidateCandidateState`
  (~2514), live-token race guards (~920/~4194), inline-reply UI in the feed.
- Tests: `tests/test_comfy_nodes_agent_*.py`, `tests/browser/roundtrip_smoke.test.mjs`.

## Sizing
~1.5 week megaplan: the edit-state authority + re-baseline (A), the published
contracts — eligibility predicate, typed `TurnOutcome`, typed envelope,
provider-readiness (B) — and parser hardening (C). It grew from "just fix
wedging" because it now establishes the contracts MP2 depends on; that investment
is what lets MP2 build on interfaces instead of reopening these files. Lands
first. Profile partnered/full, vendor codex.

## Pre-req (land before the megaplan)
Commit today's two live-verified fixes so the run starts from clean main:
- Clarify renders as a question (`CLARIFY` state; no no-op Apply candidate).
- Removed the redundant post-apply repaint; scoped the #9 redraw assertion.
