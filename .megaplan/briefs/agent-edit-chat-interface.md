# Megaplan brief — Agent-edit as a chat interface

> Depends on the session-state megaplan (`agent-edit-session-state.md`) landing
> first: a chat thread is only viable on a session that never wedges
> (`StaleStateMismatch` recovery + re-baseline) and that carries cross-submit
> memory. This plan absorbs the "conversational clarify" work (formerly
> workstream B of the session-state brief) and elevates it to "the whole panel
> is a conversation."
>
> **CONSUMES (does not reimplement) the contracts MP1 publishes in
> `agent-edit-contracts.md`:** §1 edit-state/baseline authority, §2 apply-eligibility
> predicate, §3 typed `TurnOutcome`, §4 typed envelope, §6 provider-readiness. This
> plan OWNS §5 — the **Conversation / Message** interaction model — and builds the
> UI on it. The UI reads `Conversation`/`Message`/`TurnOutcome`/`eligibility()`/
> `readiness()`; it must NOT re-derive state from raw envelope flags or stitch raw
> artifacts.

## Outcome
The VibeComfy agent-edit panel becomes a **chat thread**, not a panel of regions.
Every message the user sends gets a **human-readable agent reply**; all the turn
machinery (search calls, batch statements, gate results, diff, audit) is
**collapsed beneath** each reply; candidate Apply/Reject is **inline** in the
message that proposed the edit; and the conversation **persists with memory** so
follow-ups ("now make it 30") continue naturally. A reviewer checks: it reads and
behaves like messaging an assistant — clean conversation on top, machinery one tap
beneath — with no loss of the current Apply/Reject/Undo/audit capabilities.

## The shift (what changes vs. today)
Today the panel is organized by **function** — fixed stacked regions (Prompt,
Activity feed, Settings, Candidate, Failure, Audit/Debug), turn-centric, reads
like a debug console. This plan reorganizes everything around the
**conversation**:

| Aspect | Now | Chat |
|---|---|---|
| Structure | Fixed regions | One thread + composer |
| Unit | A "turn" + status badge | message (user) ↔ reply (agent) |
| Agent output | candidate + terse status | **always** a natural-language reply |
| Detail | always-on across regions | **collapsed beneath each reply** |
| Apply/Reject | separate region | **inline in the proposing reply** |
| Clarify | turn ends; re-submit | question bubble; reply in place |
| Memory | cold-start each submit | continuous |

## Holistic UX: element placement (the design of record)

**Organizing principle:** every element is either (a) **inside a turn** bubble
(per-exchange), (b) **inside Settings** (global config), or (c) **part of the
frame** (header / thread / composer). If it is neither turn-specific nor global
config, it is minimal chrome. Debug lives behind a Settings/dev toggle.

**The frame, top → bottom:**
- **Header (top):** title · connection dot (provider ready/not) · **＋ New
  conversation** · **⚙ Settings**. (New-conversation and Settings sit together
  at the top.)
- **Thread (middle, scrollable):** user + agent bubbles, oldest→newest, newest at
  the bottom, auto-scroll.
- **Composer (bottom):** input + Send. The conversation "starts from the bottom"
  and grows upward.

**Persistence:** the conversation **survives page refresh** — the active
`session_id` is remembered (localStorage, keyed per workflow — see open
questions) and the thread **rehydrates from the server `editor_sessions` turn
store** (turns are already persisted to disk) on load. It **only resets** via
**＋ New conversation**, which starts a fresh `session_id` and re-baselines to the
current canvas.

| Current panel element | New home |
|---|---|
| Edge "✨ VibeComfy Agent" tab | Keep — opens the panel |
| Title / subtitle | Minimal header |
| Status badge (IDLE/SUBMITTING/CLARIFY…) | Removed as top-level; expressed by the live "working…" bubble + each reply's own state |
| Meta row (session / turn / baseline hashes) | Debug-only (dev toggle) |
| Prompt textarea + Submit | The composer (bottom), always present; Submit → Send |
| Activity turn feed | Dissolved into the thread; each turn = an agent reply bubble; reasoning/statements/diagnostics/outcome under "Show details ▸" in that bubble |
| Candidate region (diff rows, affected-node preview, queue blockers, artifacts) | Nested in the reply that proposed the edit; bubble text = one-line summary; details on expand |
| `canvas_apply_allowed` / `queue_allowed` booleans | Apply button enabled/disabled + reason tooltip; raw booleans → debug |
| Apply / Reject / Undo | Inline in the relevant reply bubble (no fixed footer) |
| Failure region | An agent reply bubble ("I couldn't, because…") + inline recovery; details nested |
| Settings (route/model/key/Save/Test/guidance) | Settings popover behind a header gear ⚙ |
| Route-resolution line | Small connection dot in header + full text in Settings |
| Audit links | Nested per-turn under "Show details" |
| Queue guard / Debug raw JSON | Deep-nested, dev-mode only |
| Close | Header ✕ |
| "Nodes 2.0 / Grab→change→replace" popup | DELETED (was `ComfyUI/custom_nodes/nodes2_poc/`, a throwaway PoC) — no longer on the panel |
| Not-set-up state (no key/provider) | Setup warning / empty-state: "Connect a provider to start" + button into Settings, shown until resolved |

## Opus layout critique — refinements & lock-in decisions (2026-06-04)
An Opus design pass against the live `vibecomfy_roundtrip.js` validated the table
(~85%) and corrected five things that would otherwise force rework. These are now
part of the design of record:

1. **A turn may BOTH edit and ask.** Edit and clarify are NOT mutually exclusive
   (they are in today's code — `renderCandidate` early-returns on CLARIFY). One
   reply bubble can carry: the summary + inline Apply/Reject for what landed, AND
   a clarify question; answering in the composer continues the session.
2. **Undo is thread-level, not per-bubble.** It pops a session-level undo stack —
   render ONE Undo affordance near the composer, visible only when the stack is
   non-empty. Do not scatter Undo onto every bubble.
3. **Detail expands inline-DOWN with the bubble's top anchored** (drop "expand
   upward" — it fights newest-at-bottom). Flatten the current two-level disclosure
   (turn chevron → "Reasoning" toggle) into a SINGLE "Show details ▸".
4. **Only the latest candidate's Apply is live.** Older proposing bubbles show
   Apply as disabled/"superseded" — clicking Apply on a stale bubble is the
   StaleStateMismatch path.
5. **The failure bubble HOSTS the re-baseline recovery button** (MP1 workstream A's
   recovery action) when the failure is a StaleStateMismatch — otherwise the
   never-wedge work has no UI surface. `user_facing_message` is the bubble text;
   kind/stage/raw go under Show-details.

Refinements also folded in: delete the dev subtitle; status badge → composer
chrome (state machine still gates the composer: locked while working, focused on
clarify); shrink the 120px monospace prompt to a 1–2 line auto-grow input
(Enter=send, Shift+Enter=newline); kill raw `canvas_apply_allowed=…` strings (→
Apply enabled/disabled + tooltip = first queue-blocker message); delete the
redundant global "Download Audit Envelope" button (per-bubble audit replaces it);
split queue-guard (blocker reason → user-facing on the bubble; hook mechanics →
debug); the working bubble needs a **Stop** (abort the in-flight POST → resolve to
"cancelled"); the **fallback message synthesizer is P0** and must read like a
sentence, not a diff row.

### Lock-in decisions (Opus defaults — confirm or override)
1. **One turn = candidate + clarify in a single bubble?** → default YES.
2. **Per-workflow vs global conversation?** → default PER-WORKFLOW (correctness:
   the baseline is per-canvas; a global thread could apply to the wrong graph).
3. **Apply live on all proposing bubbles or only the latest?** → default ONLY THE
   LATEST; older = disabled/"superseded".
4. **Where does Undo live?** → default ONE thread-level Undo near the composer,
   shown only when the undo stack is non-empty.
5. **Expand direction?** → default INLINE-DOWN, anchor bubble top (drop "upward").
6. **Fallback synthesizer blocking/P0?** → default YES, ship before the thread UI.
7. **Setup warning blocks send or just warns?** → default BLOCKS (composer disabled
   when `provider_available === false`).
8. **Collapsed bubble anatomy?** → default reply text + Apply/Reject (+ recovery on
   failure) visible; everything else behind one "Show details ▸".

## Scope — IN
1. **Conversation thread UI.** Replace the stacked-region layout with a scrollable
   message thread + a single composer. User messages and agent replies are
   bubbles. **Ordering: newest-at-bottom (classic messaging — history scrolls up,
   auto-scroll to the newest reply on each turn).**
2. **Every turn ends with a message (invariant).** A turn terminates in exactly
   one user-facing message bubble — never a silent result. Clarify is just one
   kind of ending message.
   - edit landed → summary ("Set KSampler steps to 28") + inline Apply/Reject
     preview on that bubble;
   - clarify → the question, answerable inline via the same composer (same session);
   - failure / no-op / budget → plain-language explanation + any recovery action.
   Enforced TWO ways: (a) a prompt contract — the agent must end every turn with a
   user-facing message; AND (b) a **backend fallback synthesizer** — if the model
   emitted no prose, synthesize the message from the diff/gate summary (e.g.
   "Changed ksampler.steps to 28") so it is never silent even when the model
   forgets. The envelope therefore always carries a non-empty message field.
3. **Collapsible turn detail beneath each reply.** The batch turns, search/`describe`
   calls, per-statement results, gate outcomes, raw diff, and audit link collapse
   under a "Show details ▸" disclosure on each agent reply. Reuse the existing
   turn-progress feed content — re-host it *inside* the reply bubble instead of a
   separate Activity region.
4. **Inline candidate review.** Apply / Reject / Undo move from the fixed Candidate
   region to controls inside the agent reply that proposed the edit. The live
   canvas preview overlay (preview-fidelity) stays as-is, triggered from that reply.
5. **Cross-submit conversation memory (absorbed from session-state workstream B).**
   Thread prior turns (user request, agent reply, user answer) into
   `build_batch_messages` so follow-ups continue with context rather than
   cold-starting.
6. **Settings popover + setup warning.** Route/model/key/Save/Test/guidance move
   into a popover behind a header gear ⚙, off the conversation surface. If no
   provider/key is configured, show a persistent setup warning / empty-state
   ("Connect a provider to start" + a button into Settings) instead of letting a
   first message fail cryptically. A small connection indicator (provider ready /
   not) lives in the header.
7. **Live progress in-thread.** While a turn runs, show a "working…" agent bubble
   that streams the existing per-turn websocket progress, then resolves into the
   final reply (don't regress the shipped turn-progress liveness).
8. **Demote debug to debug.** Session/turn/baseline hashes, raw gate booleans, and
   the raw response JSON move behind a dev toggle / deep "Show details" — never
   top-level chrome.
9. **Persistence across refresh.** Remember the active `session_id` (localStorage)
   and rehydrate the thread from the server `editor_sessions` turn store on load,
   so a refresh keeps the conversation.
10. **＋ New conversation button** (header, next to ⚙ Settings): clears the thread,
    starts a fresh `session_id`, and re-baselines to the current canvas. This is
    the ONLY thing that resets the conversation.
11. **Leftover "Nodes 2.0" test widget — DONE (deleted 2026-06-04).** It was a
    standalone PoC custom node at `ComfyUI/custom_nodes/nodes2_poc/` (frontend-only,
    no backend nodes, nothing depended on it); removed. Gone on the next 8199
    restart. No further work — listed only for the record.
12. **Empty/welcome state** (fresh conversation) distinct from the **setup warning**
    (no provider configured).

## Three-lens design (agent-interaction · visual · data) — 2026-06-04
Three blind subagents (Codex × interaction, Opus × visual, Codex × data) analyzed
this against the live code; they cross-validated the key decisions (edit+clarify
one bubble, latest-Apply-only, per-workflow, synthesizer P0). Load-bearing
results, now design of record:

### Agent interaction & the message contract (Lens 1)
- **`message` is the public contract** — make it non-empty for EVERY terminal
  outcome (today it is just "prose outside the ```batch fence" and can be empty:
  `agent_provider.py:133`; envelope forwards `state.user_message`:
  `agent_edit.py:2082`).
- **Per-action message:** model prose preferred, but the **backend synthesizer is
  authoritative after gates** — the model writes its prose *before* gate results
  exist, so for partial-landing/failure the backend must own the final sentence.
  Synthesis precedence: landed statements → `done_summary` → first diagnostic →
  budget summary; sentence-shaped, not diff rows.
- **Prompt contract:** add a "User-facing reply" instruction under `Envelope:`
  (`agent_provider.py:216`) requiring 1–2 natural sentences before the fence on
  every turn (search-only, edit, partial, done, clarify, failure, no-op).
- **Two-tier nudge:** valid batch but empty prose → retry once with a targeted
  "your reply was empty" nudge before applying; neither prose nor batch → the
  existing malformed path (`agent_provider.py:783`), strengthened.
- **Memory = hybrid:** a compact "Conversation so far" block + the last 3 exchanges
  replayed as real user/assistant messages + an "already applied to baseline"
  ledger; older turns summarized to ~1500 chars.
- **Edits-and-asks = one envelope/bubble:** `message` + `clarification_required` +
  `clarification_message` + landed candidate + Apply/Reject. (Today `clarify()` is
  an early terminal *before* applying — `agent_edit.py:985` — this must change.)

### Conversation data model (Lens 3)
**Build it as the `contracts.md` §5 interaction layer, NOT as scattered artifacts.**
The UI works against a `Conversation = {id, workflow_key, baseline,
parent_session_id?, messages: Message[]}` with one API (`load` / `list(workflow_key)`
/ `append`); a `Message{role, text, turn_id?, outcome?: TurnOutcome}` of
`role:"agent"` just wraps a §3 `TurnOutcome` + text. The files below are the
*materialization* of that model — `chat.json` materializes a `Message`,
`index.json` materializes `list()` — but the UI never stitches raw artifacts; it
loads a `Conversation`.
- **Server disk is the source of truth** (`out/editor_sessions/<sid>/turns/<id>`,
  `turn_dir_for` `agent_session.py:59`); **localStorage holds only pointers**
  (`workflow_key → active_session_id` + UI-only state), never authoritative
  messages.
- **Per-workflow key = an opaque UUID embedded in the workflow JSON**
  (`graph.extra.vibecomfy.agent_workflow_id`), created on first panel open — NOT
  the structural graph hash (that changes on every edit:
  `vibecomfy_roundtrip.js:1230`).
- **Rehydrate on refresh** from `session_state.json` + sorted `turns/NNNN`: user
  text from `request.json` (`task`), agent reply from `response.json.message`
  (fallback `messages.jsonl`). Backend fixes needed: make `response.json`
  **unconditional** (not idempotency-gated) and add a small derived **`chat.json`**
  per turn as the stable UI-load artifact.
- **History list** = a denormalized **`editor_sessions/index.json`** manifest
  (rows: session_id, workflow_key, title from first task, created/updated,
  turn_count, last_turn_state, baseline) updated on allocate/accept/reject, with a
  rebuild-scan fallback. Surfaced via the header `＋▾` dropdown (minimal, v1).
- **Two new GET endpoints:** `…/agent-edit/session?session_id=` and
  `…/agent-edit/sessions?workflow_key=`.
- **Loading a past conversation:** always *viewable*; *resumable* only if workflow
  key matches AND current structural hash == server baseline AND no newer pending
  candidate. Otherwise offer **"Continue from current canvas"** → a new session
  with `parent_session_id`. **Never silently re-baseline on open** (consistent with
  MP1's explicit-recovery rule).
- **Lifecycle:** New conversation = fresh session + move the active pointer; never
  delete old data; retention last-N / age-cap; multi-tab via the existing session
  lock (`agent_session.py:77`) + a BroadcastChannel to sync the active pointer.

The full per-state visual spec / ASCII wireframes live in the companion
`agent-edit-chat-wireframes.md`.

## Scope — OUT / anti-scope
- Do **not** change the session/baseline protocol, gates, apply engine, or hashing
  — that is the session-state megaplan's job; this plan consumes its API.
- Do **not** rebuild the preview overlay or the per-turn detail *content* — re-host
  the existing feed inside the chat, don't reimplement it.
- No new model route or transport; reuse the existing endpoints + `/ws`.
- Not a general ComfyUI chat assistant — scope is strictly the agent-edit panel.

## Locked decisions
- Build on the shipped `CLARIFY` state, `VC_COLORS`, `invalidateCandidateState`,
  the turn-progress feed, and the preview overlay — extend/re-host, don't replace.
- The conversation is keyed by the existing `session_id`; memory rides in the
  existing `out/editor_sessions/<sid>/turns/...` store.
- Model route stays `deepseek-v4-pro`.
- Apply/Reject/Undo semantics and the audit trail are preserved exactly — only
  their placement (inline, in-thread) changes.

## Open questions (planner resolves)
- ~~Ordering~~ — DECIDED: newest-at-bottom, auto-scroll on each new reply.
- How much detail shows **collapsed-by-default** vs on expand (recommend: only the
  one-line reply + inline Apply/Reject visible; everything else behind "Show
  details").
- Memory shape: replay prior turns as chat messages vs. a compact "conversation so
  far" block into `build_batch_messages` (shared question with the session-state
  brief — coordinate).
- Whether very long threads truncate/summarize old turns to bound prompt size.
- **Per-workflow vs. global conversation:** ComfyUI has multiple workflow tabs;
  the agent edits a specific graph and the baseline is per-canvas. Recommend
  keying the conversation (and its persisted `session_id`) **per workflow** —
  switch tabs → that graph's conversation; New conversation resets the current
  one. (Alternative: one global thread. Decide.)
- **Canvas coupling:** if the user hand-edits the canvas between turns, the next
  turn re-baselines (MP1), and the chat may drop a subtle "(you changed the
  canvas)" note; hovering a reply could re-highlight the nodes it touched.
  Decide how visible this is in v1.
- **Cancel a running turn:** the "working…" bubble should offer a stop (abort the
  in-flight POST) since turns run 30-60s.
- Exact collapsed-bubble anatomy: what the one-line reply shows vs. the inline
  Apply/Reject vs. the "Show details" disclosure (recommend: reply text +
  Apply/Reject visible; all machinery behind the disclosure).
- Conversation history — PROMOTED to a **minimal v1** (both the visual and data
  lenses showed it's cheap and non-cluttering): a lazy dropdown under the header
  `＋▾`, backed by `index.json`, scoped to the current workflow. Full multi-pane
  history management remains future.

## Constraints
- No regression in preview-fidelity, turn-progress liveness, or
  Apply/Reject/Undo/audit behavior.
- `pytest tests/test_comfy_nodes_agent_*.py` green (modulo 2 known baseline fails);
  browser smoke green; add browser-smoke coverage for the thread flow.
- DeepSeek key stays in `~/.hermes/.env`.

## Done criteria
- Submit a message → an agent reply bubble appears with a one-line summary; the
  turn machinery is collapsed beneath it and expands on click.
- A clarify reply is answered inline and the next reply lands the edit using the
  answer (memory proven end-to-end, live in the browser).
- Apply/Reject/Undo work from inside the reply bubble; audit links intact.
- The panel reads as a conversation top-to-bottom; no fixed Activity/Candidate
  region remains.
- Live "working…" progress still streams per turn.

## Touchpoints
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` — the bulk: replace
  `renderAgentPanel`'s region layout with a thread renderer; re-host the
  turn-progress feed + candidate controls inside reply bubbles; composer; the
  CLARIFY inline-reply; settings header.
- `vibecomfy/comfy_nodes/agent_provider.py` — `build_batch_messages` conversation
  threading; the "always emit a user-facing message" prompt contract.
- `vibecomfy/comfy_nodes/agent_edit.py` — every terminal outcome carries a
  non-empty natural-language `message` (the synthesizer); make `response.json`
  unconditional + write a derived per-turn `chat.json`; the edits-and-asks
  envelope (message + clarification + landed candidate); two new GET endpoints
  (`session`, `sessions?workflow_key`).
- `vibecomfy/comfy_nodes/agent_session.py` — `editor_sessions/index.json` manifest
  (build/update on allocate/accept/reject + rebuild-scan fallback);
  `parent_session_id` on "continue from current canvas".
- `vibecomfy/comfy_nodes/agent_provider.py` — the "User-facing reply" prompt
  contract; the two-tier empty-prose nudge; conversation-memory threading
  (compact block + last-3 replay + applied-ledger).
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` — workflow-UUID in
  `graph.extra`; localStorage `workflow_key → active_session_id`; rehydrate-on-load;
  BroadcastChannel multi-tab sync; the whole thread/composer/header render.
- Tests: `tests/browser/roundtrip_smoke.test.mjs` (thread flow, inline apply,
  collapsible detail, inline clarify-answer, refresh-rehydrate, superseded Apply),
  `tests/test_comfy_nodes_agent_*.py` (message-always-present, synthesizer,
  edits-and-asks envelope, index manifest, session GET endpoints).

## Sizing
One ~1-2 week megaplan, sequenced **after** the session-state megaplan. Largely
frontend, with a backend slice for conversation memory + the always-reply
envelope contract. Profile partnered/full, vendor codex.
