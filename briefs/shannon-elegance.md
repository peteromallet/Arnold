# Shannon worker: elegant refactor + vendored fork + maximal tmux terminal-fidelity

## Outcome
Refactor `megaplan/workers/shannon.py` from its accreted current form into clean
**policy/mechanism abstractions**, and **vendor the `@dexh/shannon` fork** to delete
the fragile runtime string-patcher — preserving current behavior exactly, and
closing every *cheap* OS-level "this is automation" tell. The result should read
beautifully and be as indistinguishable from a normal interactive terminal session
as the tmux approach allows (see anti-scope for the hard ceiling).

## Background (the planner won't have this context — read it)
The current `shannon.py` was committed on this branch (`feat/shannon-session-strategy`,
`d2cd6a07`). It added: a randomized session-continuity strategy (never plain-resume;
shed via `/clear`/`/compact`/fresh), slash-command completion + paste-first-turn via an
in-place runtime patch to the installed `@dexh/shannon` `index.ts`
(`_ensure_shannon_parent_timeout_control`), and a pile of correctness fixes. Four
adversarial reviewers concluded the **in-place patching is the root fragility**
(concurrency torn-writes, helper-propagation gaps, anchor drift vs stock 0.0.2) and
converged on **vendoring** as the fix. 65 unit tests pass; `/compact`, `/clear`, and a
91KB paste were live-proven.

## Scope (IN)
1. **`ShannonConfig` dataclass** — load every Shannon knob once (from profile + env +
   state), replacing the ~dozen scattered `_shannon_*_enabled()/_probability()/_seconds()`
   readers. Preserve all existing env-var names for back-compat.
2. **Pure, seeded policy**: `plan_session(step, *, stored_id, fresh, cfg, rng) -> SessionPlan`
   returning `SessionPlan(kind, session_id, pre_turns: tuple[Turn,...], main: Turn, voice)`
   and `Turn(session_id, resume, body, delivery, expect, timeout)`. All new/resume/
   compact/clear/readiness selection lives here, ONLY here. Deterministic given the rng.
3. **One executor**: `run_turn(turn, ctx) -> TurnResult` — the single place that builds
   argv (`-p` vs `--input-format=stream-json`; `--resume` vs `--session-id`), pipes stdin,
   sets timeout/idle/liveness/tmux, runs `run_command`, and extracts the landed session id.
   Plus one `session_id_of(raw)` (NDJSON + legacy-array + dict). `run_shannon_step` becomes
   a thin orchestrator: build config → plan → run pre_turns → run main → parse/repair.
4. **Vendor the fork**: copy `@dexh/shannon` `index.ts` into `vendor/shannon/`, apply ALL
   megaplan patches statically (turn-timeout, tool_use guard, slash-completion,
   paste-first-turn, `sendPrompt` stdin `load-buffer`+`paste-buffer -p`, root-safe args,
   startup-enter, AND native `SHANNON_TMUX_SESSION_NAME` honoring). Run `bun vendor/shannon/
   index.ts`. **Delete** `_ensure_shannon_parent_timeout_control`, the support-detection
   helpers, the version sentinels, the atomic-write dance — all moot once we own the source.
5. **Close cheap structural tells** (fold into ShannonConfig): neutral deterministic tmux
   name (drop `megaplan-`/`step` tokens); scrub `MEGAPLAN_*`/`SHANNON_*` from the inner
   claude env; write run artifacts out-of-tree (no `*_shannon_prompt.txt` in cwd); per-run
   `CLAUDE_CONFIG_DIR` so `/clear` session-file churn doesn't pile up in the user's
   `~/.claude`.
6. **Seed + record the randomness**: seed `rng` per `(plan, step, iteration)`; log the
   chosen `SessionPlan` into state/receipt. Restores reproducibility + bake-off fairness
   while keeping the randomness Peter wants.
7. **Optional keystroke-emulation mode** (off by default): `send-keys` per-char with sampled
   inter-key delays instead of one paste. The one OS-timing tell tmux *can* address. Mark it
   explicitly cosmetic (the model never sees keystroke cadence); a stretch goal.

## Anti-scope (do NOT do)
- **No print-mode / Agent-SDK rewrite** — that's a separate architectural decision.
- **Do NOT try to hide the `bun`/`python` orchestrator process tree** — impossible on tmux,
  and the agent can't perceive it. This is the hard ceiling on "looks like a real terminal."
- **Do NOT change the session-strategy POLICY** (keep randomized clear/compact/new — Peter's
  call) or the prompt **`voice`** (harness-announced vs natural is a *separate, measured*
  experiment). DO make `voice` a clean field on `SessionPlan` so that A/B is trivial later.
- **Behavior-preserving**: change structure + vendoring, not *what* the worker does.
- Touch ONLY shannon-related files. The repo has ~34 unrelated uncommitted files from
  concurrent work — do not stage, modify, or depend on them.

## Locked decisions
- Vendor the fork; run `bun vendor/shannon/index.ts`; patches applied statically; runtime
  patcher deleted.
- Abstraction shapes as in Scope #1–3.
- Keep randomness, seeded + recorded.
- Preserve all current env-var knobs (read through `ShannonConfig`).

## Open questions (resolve in prep)
- Does the vendored `index.ts` have runtime deps (e.g. `commander`)? If so, make them
  resolvable for `bun vendor/shannon/index.ts` (vendored `node_modules`? a minimal
  `package.json` + `bun install`? bun auto-install?).
- How to keep the vendored fork maintainable vs upstream (a `VENDOR.md` recording the diff,
  or a regen script)?
- Current stock 0.0.2 has NO `megaplanTmuxSessionName` symbol — find how stock derives the
  tmux session name and add native `SHANNON_TMUX_SESSION_NAME` honoring there (fixes the
  dead-anchor / orphan-reaping gap).

## Constraints
- All 65 tests in `tests/test_workers_shannon.py` pass (update to the new structure,
  preserving intent; the `_assume_shannon_patched` autouse fixture should become moot/simpler
  once vendored).
- Cross-user safe: a fresh clone with only the vendored fork must work end-to-end (no reliance
  on a separately-installed `@dexh/shannon`).
- No orphan-reaping regression (vendored fork honors `SHANNON_TMUX_SESSION_NAME`).
- `run_command` already supports `stdin_text`; avoid changing `_impl.py` unless strictly needed.

## Done criteria
- `shannon.py` reads as **config → pure plan → uniform execute**; the readiness/op/repair/main
  turns are all `Turn`s through one `run_turn`. Runtime string-patcher gone.
- 65 tests green + new tests: `plan_session` purity + seeded reproducibility (same seed →
  identical `SessionPlan` sequence), `session_id_of` across formats, and a non-mocked test
  that runs the vendored `bun vendor/shannon/index.ts` for a trivial turn.
- Live proofs re-pass against the vendored fork (document the runs in the PR/notes):
  `/compact` completes in ~compaction-time not the timeout; `/clear` rotates+resumes the new
  id; a ~90KB multi-line prompt is delivered byte-exact as one message.
- A short tells checklist: each closeable tell closed; the irreducible ones (process tree;
  keystroke cadence unless the optional mode is enabled) documented as out-of-scope-on-tmux.

## Touchpoints
`megaplan/workers/shannon.py`; new `vendor/shannon/` (`index.ts` + dep manifest + `VENDOR.md`);
`tests/test_workers_shannon.py`; possibly `megaplan/_core` for the run-dir / config-dir;
`megaplan/workers/_impl.py` only if `run_command` genuinely needs a tweak (it should not).
