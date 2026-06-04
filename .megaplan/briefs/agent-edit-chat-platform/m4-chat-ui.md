# M4 — Chat UI (the visible redesign)

Builds the conversational panel on M1–M3's contracts. Consumes §1–§5. Visual spec:
`agent-edit-chat-wireframes.md`.

## Outcome
The agent-edit panel reads and behaves like messaging an assistant: one conversation
thread, composer at the bottom, machinery one tap beneath each reply, settings in a
popover, a setup warning when unconfigured. No fixed Activity/Candidate/Settings
region remains. Reviewer checks: submit → reply bubble with the turn detail collapsed;
clarify answered inline continues; Apply/Reject/Undo work; the preview highlights the
real field and shows its new value; verified live in the browser.

## Scope — IN (per agent-edit-chat-wireframes.md)
1. **Frame:** header (title · connection dot · `＋` New conversation · ⚙ Settings · ✕)
   / scrollable thread (newest at bottom) / bottom composer. The thread shows the
   **last 5 messages** (v1) with a small **"session: <path>"** link to the JSON for
   full detail. NO history dropdown in v1 (deferred — ticket).
2. **Bubbles:** user (right) / agent (left); each agent reply = the `message`, with
   one-tap "Show details ▸" (inline-down, bubble-top anchored) revealing the turn
   machinery; collapsed bubble = reply text + Apply/Reject (+ recovery on failure).
3. **Inline candidate controls** driven by `eligibility()` (§2): latest candidate
   Apply live; older = disabled/"superseded" + tooltip; blocked = dim + first-blocker
   reason. ONE thread-level Undo near the composer (only when undo stack non-empty).
4. **Preview overlay renders the §3 `FieldChange` contract** — highlight the real
   changed field and show its new value (kills the positional-guess + no-value bugs).
5. **Clarify inline:** question bubble; composer flips to "Answering…"; reply
   continues the same session. A turn can show Apply/Reject AND a question
   (`edit+clarify`).
6. **Settings popover** (route/model/key/Test) + a Developer section (hashes, raw
   booleans, raw JSON). **Setup warning blocks send** via `readiness()` (§6) when no
   provider configured. Empty/welcome state with tappable example prompts.
7. **Working state** streams the per-turn progress then collapses; a **Stop** aborts
   the in-flight turn → "cancelled".
8. **Session-file link** (full detail) — a small "session: out/editor_sessions/<id>/"
   affordance. NO history dropdown / past-conversation browser in v1 (deferred to the
   `agent-edit: full conversation history…` ticket).
9. **Frontend-shadow deletion + ComfyUI adapter** (deeper-seam absorption): delete
   client-side derivation wherever §2/§4 now provide truth (structural projection,
   route fallbacks, queue-blocker normalization, apply booleans); remaining client
   checks renamed as explicit race-guards; route the fragile ComfyUI/LiteGraph hooks
   (`graph.clear/configure`, `onDrawForeground`, `app.queuePrompt`, `registerExtension`)
   through ONE capability/adapter module with version tests.

## Locked decisions
- Newest-at-bottom; one thread-level Undo; latest-Apply-only; expand inline-down.
- Reuse VC_COLORS, the turn-progress feed content, the preview overlay; extend, don't
  replace.
- The UI reads `Conversation`/`Message`/`TurnOutcome`/`eligibility()`/`readiness()`;
  it must NOT re-derive state from raw flags or stitch raw artifacts.

## Open questions (planner resolves)
- M4a/M4b split decision (see sizing) — adapter vs visual rebuild — made at planning.
- Collapsed-bubble exact anatomy; history-dropdown depth.

## Constraints
- No regression in preview-fidelity, turn-progress liveness, Apply/Reject/Undo/audit.
- Browser smoke green + new coverage (thread flow, inline apply, collapsible detail,
  inline clarify-answer, refresh-rehydrate, superseded Apply).

## Done criteria
- Reads as a conversation top-to-bottom; every wireframe state renders; no fixed
  region remains; preview shows the real field + new value; verified live.

## Touchpoints
- `web/vibecomfy_roundtrip.js` (the bulk: replace `renderAgentPanel` region layout
  with the thread; re-host turn-progress + candidate controls in bubbles; composer;
  CLARIFY inline; settings popover; the capability/adapter module; overlay renders
  `FieldChange`), tests (`roundtrip_smoke.test.mjs`).

## Anti-scope
- Don't change the session/baseline protocol, gates, apply engine, hashing, or the
  conversation API — consume them. Don't reimplement the preview overlay's content,
  just feed it the §3 contract. Not a general ComfyUI chat assistant — only the
  agent-edit panel.

## Topological / sizing note
Partial topological (the LiteGraph adapter reshapes shared UI integration). Largest
sprint; the ONE >2-week split-watch — if it overruns, split **M4a (adapter /
capability layer)** from **M4b (visual rebuild)** at planning. Profile:
`partnered/full/high+prep` @codex (prep to discover ComfyUI hook/version behavior).
