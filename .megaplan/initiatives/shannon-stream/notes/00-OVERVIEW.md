# Epic: Shannon — headless stream-json channel (replace tmux puppeteering)

**Goal (one sentence):** replace Shannon's tmux-puppeteering of the interactive `claude` TUI with a
headless `claude --print` stream-json channel behind a uniform engine interface, plus a blunt concurrency
cap and a proven API-billing escape hatch — durably closing the ticket's 8 failure classes.

**Reference design:** `docs/shannon-stream-channel-plan.md` (full architecture, sequence, and the
validation trail). This overview is the operational header; each milestone brief is self-contained.
**Originating ticket:** `01KTVV4ANX9MVKBFPRZX6F1AEH`.

## How this was validated (so the planner does not relitigate)
- A live Phase-0 spike on `claude` 2.1.173 PROVED: headless `--print --output-format=stream-json` bills
  the **subscription** (`apiKeySource: none`), keeps full tool/skill/subagent parity, writes a real
  transcript (once `CLAUDECODE` is scrubbed), gives a structured `result` turn-end + an inline
  `rate_limit_event`, supports multi-turn + `--resume`, and runs tools under `--permission-mode
  bypassPermissions` (verified by a file on disk).
- Two 10-agent DeepSeek panels (load-bearing + system bets) and two Codex high-abstraction reviews
  refined the plan. Their corrections are already baked into the briefs.

## Milestones (partnered // full; vendor codex)
- **M1 — invocation seam.** `run_step -> WorkerResult` hosts all 3 engines; add typed `rate_limit`.
  Behavior-preserving (kept a clean, green-suite-verifiable first commit — NOT merged into M2).
- **M2 — ShannonStreamWorker + drift defense.** The new headless channel (additive, flag-OFF).
- **M3 — rollout.** Four internal parts in order: A concurrency cap (replaces the governor) → B API-adapter
  proof (validated subscription→API flip) → C sampled shadow (parity gate, N≥5) → D flag-gated cutover,
  tmux retained. (Condenses the former M3 cap+adapter and M4 shadow+cutover.)

Dependency: strict M1 → M2 → M3. Each handoff is a written artifact the next milestone cites
(the `WorkerResult` contract → the worker → the cap+cutover flag).

## EPIC-WIDE INVARIANTS (every milestone obeys; repeated in each brief)
1. **Dogfood discipline — additive + flag-OFF.** `ShannonStreamWorker` is NEW code alongside the existing
   tmux `shannon.py`; the new path is gated OFF by default. The running engine keeps executing the OLD
   tmux path through M1–M3, so the chain never depends on half-built code. Cutover is M4 only.
2. **Never drive the rewrite with the thing being rewritten.** Vendor is **codex**; execute is pinned to
   codex (NOT the complexity router, which would send c4/c5 tasks to Claude/Shannon — the exact path
   under reconstruction). No phase of this epic runs through Shannon.
3. **Behavior-preserving where claimed, gate-backed.** M1 changes no behavior; the full green suite is the
   backstop and must stay green at every milestone boundary.
4. **Keep tmux.** Do NOT delete the tmux path. It is the maintained fallback until the API channel is
   independently production-proven (a separate, later decision — explicitly out of scope here).
5. **Tell the truth about safety.** The confinement boundary is the **OS user**, not the worktree
   (`bypassPermissions` ignores cwd; the megaplan `runtime.sandbox` is not installed on the Claude path).
   Either install the sandbox on the new path or document the OS-user boundary — do not claim the worktree
   confines anything.

## Anti-scope (epic-wide)
- No cross-engine rate-governor (deferred until a real billing boundary exists — a blunt cap replaces it).
- No tmux retirement. No changes to Codex/Hermes invocation beyond wrapping them in the seam.
- No migration to API billing (only *prove* the adapter + ship the trigger list).
