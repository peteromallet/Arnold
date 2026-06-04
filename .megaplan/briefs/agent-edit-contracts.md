# Agent-edit — shared architecture contracts

> The canonical interfaces between the **execution layer** (sessions / turns /
> baseline — what runs an edit) and the **interaction layer** (conversation /
> messages / UI — how the user talks to it). Today the codebase has the execution
> layer but no interaction layer, so the chat is otherwise simulated on scattered
> artifacts. This doc defines the abstractions once and assigns ownership.
>
> **Ownership / seam:** the **session-state megaplan (MP1)** implements and
> *publishes* contracts §1–§4 (execution-side). The **chat-interface megaplan
> (MP2)** implements §5 (interaction-side) and *consumes* §1–§4. MP2 must not
> reach around these into raw dicts.

## §1 Edit-state / baseline authority (MP1)
**Problem it removes:** baseline is mutated/compared in ≥4 places (`accept_turn`
`agent_session.py:811`, ingest compare `agent_edit.py:693`, client `undo`
`vibecomfy_roundtrip.js:4492`, MP1 re-baseline) — every new pathway breeds a new
`StaleStateMismatch`.

**The abstraction:** ONE owner of "current baseline" and *every* transition to it:
`accept`, `undo`, `rebaseline`, `continue-from-canvas`. All transitions are
**CAS-guarded** (succeed only if the session baseline still equals the caller's
last-known baseline; reject on concurrent drift) and write an audit event. No code
outside this owner writes `baseline_graph_hash`.

## §2 Apply-eligibility predicate (MP1)
**Problem it removes:** "can I apply candidate X right now?" is recomputed from
`live_canvas_token` + `canvas_apply_allowed` + "is this the latest turn" +
queue-blockers, in different places.

**The abstraction:** a single predicate `eligibility(candidate, liveCanvas) ->
{ applyable: bool, reason: string }`. Encodes: latest-candidate-only, superseded,
queue-blocked, stale-canvas. The UI's Apply enabled/disabled + tooltip, the
supersede rule, and stale detection are all this one call.

## §3 TurnOutcome — typed discriminated union (MP1)
**Problem it removes:** outcomes are implicit and treated as mutually exclusive
(`clarify()` early-returns *before* apply, `agent_edit.py:985`) — which is exactly
why "edit + ask" is currently impossible.

**The abstraction:** a tagged result every turn produces, both sides agree on:
```
TurnOutcome =
  | { kind: "edit",        message, candidate, eligibility, changes: FieldChange[] }
  | { kind: "clarify",     message /*the question*/ }
  | { kind: "edit+clarify",message, candidate, eligibility, changes, clarification }
  | { kind: "failure",     message, failureKind, recovery? }
  | { kind: "noop",        message }
  | { kind: "budget",      message }

FieldChange = { uid, field_path, old, new, widget_hint? }   // authoritative, from the executed ops
```
`edit+clarify` is a first-class variant, not a hack. **`changes` is the
preview/diff contract** — authoritative per-field old→new data carried from the
executed ops (delta ops already hold `target=[scope,uid,field_path]` + `value`,
`edit_ops.py:101`), so the overlay highlights the *real* field and shows the new
value instead of guessing a widget index client-side (today `ContentEdits` is
UID-buckets only — `reconcile.py:119` — and `changedWidgetIndices` is a positional
array-diff guess, `vibecomfy_roundtrip.js:2587`).

## §4 Response envelope contract (MP1)
**Problem it removes:** the envelope is ~15 loose optional flags and booleans leak
to the UI as text (`canvas_apply_allowed=true`).

**The abstraction:** a typed/documented envelope the UI *reads as state*, never
re-derives. Always carries: a **non-empty `message`** (see MP2 §contract for the
synthesizer that guarantees it), the **`TurnOutcome`** (§3), the candidate +
**`eligibility`** (§2), `audit_ref`. Raw gate booleans / hashes are debug-only
fields, not UI inputs.

## §5 Conversation / Message model (MP2)
**Problem it removes:** the UI reconstructs "a conversation" from 5 sources
(`request.json` + `response.json` + `messages.jsonl` + `chat.json` + `index.json`
+ localStorage), which is why a parallel half-model (`chat.json`) was being added.

**v1 (slim — see M3 scope decision):** just enough to show the **last 5 messages** +
thread the last 5 to the agent.
```
Message = { role: "user"|"agent", text, turn_id?, outcome?: TurnOutcome }
```
- A `Message` of `role:"agent"` wraps a `TurnOutcome` (§3) + its text.
- Materialized by the execution layer's turn store: one `chat.json` per turn is the
  read unit; the UI loads the last-5 from the active session's turns (active
  `session_id` in localStorage). Full detail = a link to the on-disk session JSON.
- NO `Conversation` aggregate / `list()` / `index.json` / per-workflow keying /
  cross-conversation access / search in v1 — deferred to the `agent-edit: full
  conversation history…` and `…per-workflow keying…` tickets. Per-turn records already
  persist on disk, so that future retrieval/history layer is additive, not a migration.

## §7 GraphRepresentation boundary (named in M1/M2; full cleanup separate)
**Problem it removes:** there isn't one "graph" — there are several with different
truths, and UI⇄IR⇄API is a lossy translation chain, not a contract (`ui_emitter.py`
states export is NOT lossless; `compile("api")` strips helpers/intent/runtime,
`workflow.py:733`). Chat will say "the graph" and mean four different things.
**The abstraction (name it now, even before the deep cleanup):** an explicit set of
named representations and which is authoritative for what —
`UI graph` (editor furniture) · `editable/IR graph` (the agent's model + identity) ·
`queue/API graph` (`compile("api")`, runtime truth) · `preview/candidate graph`.
Every contract above states which representation it speaks in (e.g. §1/§4 reason in
the IR/structural hash; the preview overlay is the candidate graph). The full
re-architecture of the translation chain is logged debt; *naming the boundary* is in
scope so nothing new is built on the ambiguity.

## §6 Provider readiness (MP1, small)
One `readiness() -> { ready: bool, reason: string }` source. The header connection
dot, the composer lock, and the setup warning all read it — not the raw
route/`provider_available`/key checks scattered today.

## Consequence if these are skipped
Without §1–§2 we keep playing StaleStateMismatch whack-a-mole (undo found one path;
superseded-Apply, continue-from-canvas, and manual edits are the next three).
Without §3–§5 the chat UI is a pile of stitches across 5 artifacts and "edit+ask"
stays a special case. These contracts are the difference between a sound layering
and a fragile bolt-on.
