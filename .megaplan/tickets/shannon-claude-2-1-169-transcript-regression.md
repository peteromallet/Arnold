# Shannon transcript detection broken by Claude Code v2.1.169 (ai-title-only transcripts)

Severity: BLOCKER for all vendor=claude phases (plan/execute/review) driven via Shannon.

## Symptom
Every vendor=claude phase times out: "Timed out waiting for Claude transcript
containing the submitted prompt in ~/.claude/projects/-private-tmp-arnold-target".
Pane shows Claude authenticated (Claude Max), trusted, and REPLYING.

## Root cause (verified 2026-06-09)
Claude Code v2.1.169, launched by vendored Shannon via `tmux new-session ... claude
--session-id <uuid>`, writes ONLY `{"type":"ai-title",...}` sidecar rows to the
polled `<sessionId>.jsonl` files (109-158 bytes each). The actual user/assistant
message rows are NOT written to any jsonl in the project folder. Proof: the ai-title
for the m0 prompt was "Lock generic Arnold substrate boundary..." (== m0-boundary-lock),
so Claude RECEIVED and understood the 19KB prompt — but megaplan reads Claude's
output from the transcript, which only contains the title.

Shannon's `rowContainsPromptAfter` (vendor/shannon/index.ts:1090) requires a
`type:"user"` row whose `message.content` === the submitted prompt; v2.1.169 never
writes that row → `waitForSessionWithPrompt` (index.ts:1053) polls until START_TIMEOUT
and throws. Raising SHANNON_START_TIMEOUT_MS to 90s does NOT help (confirmed).

Normal interactive Claude sessions (e.g. the operator's own) DO persist full
transcripts in real time — so the regression is specific to Shannon's launch of 169.

## Fix directions (need investigation)
1. Find where v2.1.169 actually persists conversation messages now (new file/format?
   the `ai-title` row type is new) and update listTranscriptPaths/readTranscript +
   rowContainsPromptAfter to read it.
2. OR switch these phases to `claude --print`/stream-json headless (output to stdout)
   instead of interactive tmux paste, bypassing transcript polling.
3. OR pin Claude Code to a pre-2.1.169 version that writes full transcripts.

## Workaround
None for vendor=claude. (vendor=codex unaffected, but the migration chain mandates
vendor=claude per docs/current-overall-goal.md.)

---
## Secondary issue (2026-06-09): parallel critique fanout — SQLite contention + rare fatal crash
The parallel critique fanout (orchestration/parallel_critique.py → _core/worker_fanout.py →
_core/hermes_fanout.py scatter_gather_processes) hits `_ProcessUnitFailure: database is
locked` under multiprocess SQLite contention. It SELF-HEALS (falls back to sequential),
but on one occasion (m1→m2 boundary) a fatal CPython interpreter crash followed
(`object address/refcount/type` dump in run_chain_cli) and killed the driver — recovered
by clearing the stale .plan.lock and relaunching (resume advanced cleanly m1→m2).
Durable fix: add SQLite busy_timeout/WAL to the worker DB access, and/or force the
multiprocessing start method to 'spawn' for the critique fanout (fork+SQLite is unsafe),
or gate parallel critique behind a robustness flag. One-off so far; monitor for recurrence.

### Refinement (2026-06-09, recurred on m2): contended DB = hermes SessionDB
parallel_critique.py:95-105 runs a hermes `AIAgent` + `SessionDB` per fanout process.
`agent/hermes_state.py` already has `sqlite3.connect(timeout=10.0)` + WAL, so the
"database is locked" is most likely on `SessionDB` (the hermes session store), which
appears to lack busy_timeout/WAL. Durable fix: give each fanout process its OWN
SessionDB path (per-worker isolation) OR add `timeout`/`PRAGMA busy_timeout` + WAL to
SessionDB. Recurred on m1 and m2 critique; SELF-HEALS via sequential fallback each time
(non-blocking). Apply between milestones (not mid-execute) to avoid disrupting an
active run, OR immediately if the associated fatal driver crash recurs (then it blocks).

---
## RESOLVED (2026-06-09) — multi-agent root-cause + fixes, commit b87c9b8b
- #4 "database is locked": ROOT = run_parallel_critique collapsed all fanout workers onto ONE shared SessionDB (constant session_key "hermes_critic"). FIX = per-check session_db_path via WorkerUnit.extra.worker_options (parallel_critique.py). Tested (63 critique tests pass).
- #3 fatal driver crash: ROOT = disk exhaustion → sqlite3.Connection.__del__ raising during interpreter-shutdown GC on a full/locked DB (fanout already uses spawn, NOT a fork bug). FIX = preflight disk guard at each milestone start in run_chain (halt clean if free < MEGAPLAN_MIN_FREE_DISK_GB, default 1.5GB). Tested (160 chain tests pass).
- #2 auto-verify deadlock: gates are correct (must-only, review.py:571); auto.py:863 patch (58c7fe95) is the right layer + sufficient. No further change.
Still OPEN: the original Shannon 2.1.169 transcript regression (claude pinned to 2.1.168 as workaround) — durable fix (read 2.1.169+ store / claude --print headless) still TODO.

---
## INVESTIGATION VERDICT (2026-06-09) — it's an Anthropic REGRESSION, durable fix = headless
- VERDICT: 2.1.169 transcript wipe is a RECURRING Claude Code data-loss bug, NOT an intentional format change. GitHub anthropics/claude-code#60984 ("JSONL only saves ai-title, no message content") — first 2.1.144/145, last-good 2.1.143; also #31610 (v2.1.70). Same ai-title-only signature; reappeared in 2.1.169. Issue's own workaround = downgrade (= our pin).
- WHERE messages go on 2.1.169: NOWHERE — lost, not relocated (no sqlite/sessions/history/tmp anywhere under ~/.claude). So "teach Shannon to read the new store" is IMPOSSIBLE.
- Nuance: intermittent/process-dependent; specifically wedges Shannon's fast-exit `claude --session-id` interactive launches.
- DURABLE FIX = (B) move vendor=claude phases to `claude --print --output-format stream-json` (headless): Claude streams assistant/result JSON to stdout, Shannon reads it directly → version-agnostic, immune to this bug class. Feasibility HIGH (single-turn-per-phase fits -p; index.ts already declares -p/--print + --output-format stream-json + emitJson/toSdk* mappers at index.ts:140-143,1374-1399). Sketch: headless branch in runShannon (index.ts:795-948) spawning `claude -p <prompt> --output-format stream-json [--session-id] [--permission-mode bypassPermissions]`, bypassing tmux new-session(854)/sendPrompt/waitForSessionWithPrompt(1053)/rowContainsPromptAfter(1090)/readTranscript(1301); workers/shannon.py builds headless argv + parses stdout stream-json. Risk MED-LOW (interactive trust/permission panes must be pre-satisfied under -p). 
- SAFE VALIDATION (no 169 needed): prototype the -p stream-json path on 2.1.168, confirm Shannon parses stdout + phase completes WITHOUT touching ~/.claude/projects/*.jsonl → transcript-independent on 168 ⇒ 169-proof by construction.
- INTERIM: hardened pin holds (symlink→2.1.168 + DISABLE_AUTOUPDATER=1 in ~/.zshrc+~/.zprofile + 2.1.169 binary deleted). Ride it for the remaining m3–m7; implement (B) as the deliberate retire-the-pin engine change.
Sources: github.com/anthropics/claude-code/issues/60984, /issues/31610

### CONSTRAINT (2026-06-09, user): `claude -p` / headless is NOT permitted — option B is OUT.
Interactive-tmux is the only allowed mode, and it REQUIRES the transcript file. Since
the messages are genuinely lost on bad versions (option A impossible) and -p is
forbidden (option B out), the durable fix is ROBUST PINNING to a known-good version,
made self-defending:
- Pin (done): symlink→2.1.168 + DISABLE_AUTOUPDATER=1 (~/.zshrc, ~/.zprofile) + 2.1.169 binary deleted.
- SELF-DEFENDING GUARD (to implement in megaplan/workers/shannon.py): before each
  claude launch, check `claude --version`; if it is a known-bad ai-title-regression
  version (2.1.69/2.1.70, 2.1.144/145, 2.1.169, env-overridable), AUTO-RE-PIN the
  ~/.local/bin/claude symlink to the configured good version (default 2.1.168) if its
  binary exists, else FAIL LOUD with an actionable message — instead of the silent
  "Timed out waiting for Claude transcript" wedge that silently kills a milestone.
- Track Anthropic fix (#60984); only unpin to a future version after verifying it
  writes full user/assistant transcript rows (not ai-title-only).
