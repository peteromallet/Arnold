# Epic — Agent-edit chat platform

From a fragile, turn-based, region-stacked panel that wedges on `StaleStateMismatch`
to a robust **conversational graph-editing interface**, built in dependency order on
one shared contract spine (`agent-edit-contracts.md`). Four sprint-sized milestones,
each ≤2 weeks, each with a published handoff artifact the next consumes.

**Spine:** `agent-edit-contracts.md` defines §1 edit-state/baseline authority,
§2 apply-eligibility, §3 typed `TurnOutcome`, §4 typed envelope, §5
Conversation/Message model, §6 provider-readiness. The epic *is* the staged
delivery of those contracts: M1 §1–§2, M2 §3–§4/§6, M3 §5, M4 the UI on all of them.

**Profiles:** all milestones partnered/full, vendor codex, unless noted.

---

## M1 — Edit-state consistency & apply-eligibility (foundation)
**Direction:** *never wedge; one owner of edit-state.*
**Scope:** §1 edit-state/baseline **authority** — a single CAS-guarded owner of every
baseline transition (accept, undo, rebaseline, continue-from-canvas); no code outside
it writes `baseline_graph_hash`. The `/agent-edit/rebaseline` endpoint; undo awaits
re-baseline; explicit one-click recovery on mismatch (never silent heal). §2
**apply-eligibility predicate** `{applyable, reason}` (latest-only / superseded /
queue-blocked / stale-canvas), replacing the scattered checks.
**Handoff:** contracts §1, §2 published + tested.
**Depends on:** nothing (foundation).
**Done:** Apply→Undo→edit→Apply never wedges; divergence → one-click recovery;
`eligibility()` drives Apply enable/disable with a reason.

## M2 — Typed result contracts & clean turn output
**Direction:** *every turn returns a typed, always-messaged outcome.*
**Scope:** §3 typed **`TurnOutcome`** discriminated union — crucially make
`edit+clarify` emittable (stop `clarify()` early-terminating before apply,
`agent_edit.py:985`). §4 **typed envelope** with an **always-non-empty `message`**:
the per-action message contract + the **backend fallback synthesizer** (sentence-
shaped, precedence landed→done→diagnostic→budget) + the two-tier empty-prose nudge +
the "User-facing reply" prompt contract. §6 **provider-readiness** single source.
Workstream C: **parser hardening** — kill the routine first-attempt missing-fence
retry.
**Absorbs (deeper seams):** collapse the protocol zoo to canonical `batch_repl`
(first task — quarantine `delta`/`full`); de-dup the worker/parent parse+message
fallback so the synthesizer is the single owner; **carry per-field `changes`
(`{uid, field_path, old, new}`) in the edit outcome** (the preview/diff contract —
today `ContentEdits` is UID-buckets only, so the overlay guesses the widget and
can't show the new value).
**Handoff:** contracts §3, §4, §6 published; ONE canonical protocol; the agent always
returns a clean typed result on a never-wedge session.
**Depends on:** M1 (envelope carries `eligibility`).
**Done:** a turn emits `edit+clarify`; `message` is never empty; first-attempt
malformed-fence retries ≈ 0; `readiness()` is one signal.

## M3 — Conversation layer (data model · persistence · memory)
**Direction:** *a persistent, per-workflow conversation the agent remembers.*
**Scope:** §5 **Conversation/Message model** + API (`load`/`list(workflow_key)`/
`append`); per-workflow **UUID keying** (`graph.extra`, not the graph hash);
persistence + rehydrate-on-refresh; `index.json` history manifest + the two GET
endpoints (`session`, `sessions?workflow_key`); `chat.json` materialization; make
`response.json` unconditional; load-past vs **continue-from-canvas** (with
`parent_session_id`); multi-tab via session lock + BroadcastChannel. **Conversation-
memory threading** so the agent continues with context (compact "conversation so far"
+ last-3 replay + applied-ledger).
**Handoff:** the Conversation API (§5) + a remembering agent.
**Depends on:** M2 (a `Message` wraps a `TurnOutcome`; memory reads prior turns).
**Done:** refresh rehydrates the thread; "now make it 30" continues; history dropdown
lists/opens past chats; resume vs continue-from-canvas both behave.

## M4 — Chat UI (the visible redesign)
**Direction:** *the panel becomes a conversation.*
**Scope:** the full panel rebuild on M1–M3's contracts, per
`agent-edit-chat-wireframes.md`: frame (header with `＋▾` + ⚙, scrollable thread,
bottom composer); bubbles with one-tap collapse/expand; inline Apply/Reject driven by
`eligibility()` (latest-live, older "superseded"); one thread-level Undo; Settings
popover + Developer section; setup warning that **blocks send** via `readiness()`;
empty/welcome state with tappable prompts; working bubble + **Stop**; inline clarify
answering; failure bubble + re-baseline recovery button; the `＋▾` history dropdown.
**Absorbs (deeper seams):** delete frontend-shadow derivation wherever a backend
contract (§2/§4) exists (remaining client checks renamed as explicit race-guards);
put the fragile ComfyUI/LiteGraph hooks behind ONE capability/adapter module with
version tests; **the preview overlay highlights the real field and renders the new
value from the §3 `changes` contract** (kills the flaky positional widget-index
guess and the "no new value shown" bug).
**Handoff:** the shipped chat interface.
**Depends on:** M1, M2, M3.
**Done:** reads as a conversation top-to-bottom; every state matches the wireframes;
no fixed Activity/Candidate/Settings region remains; verified live in the browser.

---

## Profiles / sizing (Codex + Opus jury, 2026-06-04 — they converged)
Run as ONE `megaplan chain` epic; do not parallelize milestones (M4 may design-review
after M3 *planning*, but implementation waits for the §5 API). Robustness `full` and
vendor `codex` throughout (wedging is UX, not a prod-data incident → not `thorough`).
**Every milestone is a premium-PLANNER case** under the topological-risk rule
(each reshapes a cross-module contract). Execute stays complexity-routed (finalize
premium floor); no `--max-execute-tier` cap.

| Milestone | Profile | Depth | Prep | Topological? | Size |
|---|---|---|---|---|---|
| **m0** test-leak cleanup (1st chain milestone; committing the 2 fixes is the manual pre-req) | `directed/full` | `medium` | no | YES (module relocation = import-graph) | small |
| **M1** edit-state authority | `partnered/full` | `high` | no¹ | YES (baseline authority across `agent_session`/`agent_edit`/gates/JS) | ~1.5 wk |
| **M2** typed contracts + protocol collapse | `partnered/full` | `high` | no | **YES — sharpest** (collapse `batch_repl`/`delta`/`full`) | ~2 wk² |
| **M3** conversation slice (SLIM v1) | `partnered/full` | `medium` | no | no (additive display + 1 pointer) | < 1 wk — merge candidate |
| **M4** chat UI + adapter | `partnered/full` | `high` | **yes**⁴ | partial (LiteGraph adapter) | ~2 wk, split-watch⁵ |

Shorthand: m0 `directed//medium` · M1 `partnered//high` · M2 `partnered//high` ·
M3 `partnered//medium` · M4 `partnered//high+prep` — all `@codex`.
No human-approval gate: `merge_policy: auto`, `auto_approve: true`, M4
`prep_clarify: false`. (`on_failure`/`on_escalate: abort` are stop-on-error safety,
not permission gates — babysit re-drives.)

**Jury divergences (resolved):**
1. ¹ M1 prep — Opus +prep (rebaseline touches the ingest/hash contract), Codex none.
   **Resolved: no prep** — that contract is already mapped in `contracts.md` §1 + two
   Codex architecture passes; prep would be redundant. Add `--prep-direction` only if
   M1 planning still looks shaky.
2. ³ M3 depth — Codex `high`, Opus `medium`. **Resolved: `medium`** — Lens 3 already
   resolved keying/rehydrate/source-of-truth, so residual planner complexity is lower
   (discount for decisions already made).
3. ⁴ M4 prep — Codex +prep (inspect LiteGraph hook + version-capability behavior
   before the adapter), Opus none. **Resolved: +prep** — discovering ComfyUI
   frontend-internal behavior is exactly what prep is for.

² M2 is internally order-sensitive: **collapse the protocol zoo to `batch_repl`
FIRST**, then `TurnOutcome`/envelope/synthesizer/readiness, then parser; parser
hardening is the only safe tail-slip if M2 overruns.
⁵ M4 is the one >2-week split candidate: if it bloats, split **M4a (adapter /
capability layer — the topologically-risky, independently-testable half)** from
**M4b (visual thread rebuild)**. Decide at M4 planning, not now.

**Biggest risk (both agents):** M2's protocol-zoo collapse is the load-bearing
topological move — a wrong consolidation topology breaks every downstream contract
non-locally; keep its premium planner and sequence the collapse strictly first.
Secondary: M4 absorbing contract fixes M1–M3 failed to publish cleanly → enforce a
contract artifact at every handoff.

**Validation pass (Opus areas → 10 DeepSeek investigators, 2026-06-04):** confirmed
M2 is the fullest milestone — the delta quarantine is a real shared-builder refactor
+ ~150-test migration, edit+clarify is 3-level code surgery (clarify currently
discards landed edits), and there is **no cancellation primitive** (M4 "Stop" needs a
new `Popen`+`/cancel`+`cancelled`-outcome, else descope to dismiss-only). Parser
hardening and cancellation are M2's slip/descope levers. M1 gains a precise
constraint (CAS after the idempotency-replay block). Intentionally NOT elevated: the
offline `object_info` gap (the live path works) and the confirmed-tiny `response.json`
fix — left as in-milestone detail.

**Scope decision (2026-06-04) — M3 slimmed.** v1 conversation = show the last 5
messages + a link to the session JSON file + last-5 agent memory + a single
localStorage active-session pointer. Everything heavier (history browser, per-workflow
`graph.extra` keying + its duplicate probe, cross-conversation agent memory, search,
relevance memory, multi-tab ownership) is DEFERRED to two future-work tickets. The
`graph.extra` probe is therefore **no longer a v1 gate**. M3 is now <1 week and a
candidate to merge into M2 (backend) + M4 (display) at chain-finalization. (The
latent `SessionStateLock` stale-lock deadlock is still worth a standalone fix; tracked
in the multi-tab ticket.)

## Dependency graph
M1 ──▶ M2 ──▶ M3 ──▶ M4   (strict chain; each consumes the prior's published contract)

## Why these cuts
- **M1 before everything:** the never-wedge invariant + eligibility is the bedrock; a
  chat that dies mid-thread is pointless.
- **M2 separate from M1:** result-*shape* (typed outcome, always-message) is a
  distinct concern from state-*consistency*; bundling them makes one oversized sprint.
- **M3 separate from M4:** the conversation can exist, persist, and be remembered
  (backend + API) and be verified headless before any pixel of the new UI — de-risks
  the biggest, most visible sprint.
- **M4 last and alone:** it's the largest (all frontend) and only safe once it can
  build entirely on stable contracts instead of reopening backend files.

## Deeper seams (Codex 2026-06-04) — dispositions
A Codex pass against the epic surfaced 9 seams beyond the six contracts. Disposition:

**Absorbed into the epic:**
- **Protocol zoo → M2 (first task).** Three live paths — `batch_repl`/`delta`/legacy
  `full` (`agent_edit.py:568`, `:2024/:2036/:2050`). M2 makes **`batch_repl` the one
  canonical product path**, quarantines `delta`/`full` behind dev-only tests, and the
  typed `TurnOutcome` wraps a single executor shape. (Fix-first #1 — every other
  contract otherwise needs compat branches.)
- **Worker/parent parse+message duplication → M2.** Runtime worker invents a fallback
  message (`megaplan_worker.py:76`) while the parent has its own parse/retry
  (`agent_provider.py:742`). M2's synthesizer must be the single owner — de-dup.
- **Frontend shadows backend → M4.** JS re-derives structural projection (`:882`),
  route fallbacks (`:154`), queue-blocker normalization (`:988`), apply booleans
  (`:4125`). M4 deletes client derivation wherever a backend contract (§2/§4) exists;
  remaining client checks are renamed as explicit race-guards only.
- **ComfyUI frontend hooks → M4 adapter.** `graph.clear/configure` (`:472`),
  `onDrawForeground` re-asserted every 1s (`:545`), monkey-patched `app.queuePrompt`
  (`:3440`), canvas-menu patch (`:4703`). M4 puts these behind ONE capability/adapter
  module with version capability tests.
- **Test-support leak → pre-M1 cleanup.** Production `guard_full_ui` imports
  `tests.support.agent_edit_normalize` (`edit_apply.py:426`). Move normalization into
  production code (tests import it, not the reverse) before M1.
- **GraphRepresentation boundary → named in M1/M2** (`contracts.md` §7); full
  translation-chain re-architecture is logged debt.

**Logged debt / future-epic prereqs (NOT in this epic — log as megaplan-tickets):**
- **Retroactive identity** (`edit_ledger.py:147` invents/repairs uids at ingest):
  make UID a first-class editor invariant — **prereq before a serious "Nodes 2.0"
  epic**, not needed for chat.
- **Schema/object_info multi-source confidence** (`agent_edit.py:1814`,
  `provider.py:405`): separate schema cleanup; for this epic only expose provenance
  in the debug panel. Bites Nodes 2.0 more than chat.
- **Generated-Python `exec`** (`agent_generated_loader.py:294`): acceptable only as
  deprecated debt once `batch_repl` is canonical (M2) — do NOT expand it; plan its
  removal separately.

## Pre-req (before M1)
1. Commit today's two live-verified fixes (clarify-as-question + redundant-repaint).
2. The test-support-leak cleanup above (small, unblocks clean M1).

## Open sizing notes
M4 is the fullest ~2 weeks; M1/M2/M3 land closer to 1–1.5 weeks each. If M1's
authority refactor proves larger than expected, M2's parser-hardening can slip into a
follow-on without blocking M3.
