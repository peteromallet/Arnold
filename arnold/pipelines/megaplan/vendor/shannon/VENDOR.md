# Vendored: @dexh/shannon v0.0.2

## Upstream source
- Package: `@dexh/shannon@0.0.2`
- Repository: https://github.com/humanlayer/shannon

## Verified-pristine source path
`~/.nvm/versions/node/v20.19.4/lib/node_modules/@dexh/shannon/index.ts.bak.megaplan-shannon`

Verified pristine via all five guard checks:
- `megaplanSlashCompletionRow` count = 0
- `isRootProcess` count = 0
- `rootSafeClaudeArgs` count = 0
- `const TURN_TIMEOUT_MS = 180_000` present
- `` const tmuxSession = `shannon-${randomUUID()}` `` present

## Vendored date (UTC)
2026-05-29

## Sentinel
Top-of-file (line 2, immediately after the shebang):
```
// MEGAPLAN_SHANNON_VENDORED v1 — patches: P1..P15
```
This is the cheap presence marker the Python side asserts via `_assert_vendored_shannon_sentinel()` to confirm all patches landed. (The Python check matches the substring `MEGAPLAN_SHANNON_VENDORED v1`; the trailing `patches: P1..PN` range is informational. As of P16 the range reads `P1..P16`.)

## Patch list

All patches are anchor-based (verbatim source-string replacement, **never** line-number). Applied in P1..P15 order. Each patch is idempotent: a second application is a no-op.

### Ordering dependencies

- **P7 → P8** (load-bearing). Both patches target the shared anchor `    let launchedWithPrompt = true;\n`. P7 *prepends* `void maybeSendStartupEnterKeys(tmuxSession);` before that line and leaves the line intact. P8 then *replaces* the (still-present) `let launchedWithPrompt = true;` line with the `!(...PASTE_FIRST_TURN...)` flag form. If P8 ran first, P7's anchor would still match in pristine source — but in the static patch order assumed by the catalog and by the regeneration recipe, P7 MUST precede P8. Applying out of order silently corrupts the launchedWithPrompt expression. Encoded by the patcher's P1..P15 ordering.
- **P3/P4/P5/P10 → P6** All four helpers (isRootProcess, rootSafeClaudeArgs, maybeSendStartupEnterKeys, slash-helpers block) prepend before the same anchor `export function buildClaudeArgs(...)`. They are applied in P3, P4, P5, P10 order; final file ordering (top to bottom) is: isRoot, rootSafe, startup-enter, slash-helpers, buildClaudeArgs.
- **P6 → P8b → P15** P6 introduces the `claudeLaunchArgs` ternary at the new-session launch site. P8b extends the non-root branch into a nested PASTE_FIRST_TURN ternary. P15 prepends `_mpEnvPrefix` into all three claude-arg arrays. P15's anchor matches the *post-P8b* form.
- **P10 → P11, P10 → P12, P10 → P13** P11/P12/P13 all reference helpers defined inside the P10 slash-helpers block (`megaplanSlashPromptMatches`, `megaplanSlashCompletionRow`, the embedded `if (cmd === "/clear")` shortcut).

---

# Patch P1 — turn-timeout-env-override

Anchor (verbatim):
```ts
const TURN_TIMEOUT_MS = 180_000;
```

Replacement:
```ts
const TURN_TIMEOUT_MS = Number(Bun.env.SHANNON_TURN_TIMEOUT_MS ?? 900_000);
```

megaplan reason: Shannon's hardcoded 180s turn timeout is too short for normal execute/critique/finalize phases; megaplan owns the timeout budget and overrides via `SHANNON_TURN_TIMEOUT_MS`.

---

# Patch P2 — tool-use-row-guard

Anchor (verbatim):
```ts
    if (textFromContent(row.message.content)) return row;
```

Replacement:
```ts
    if (row.message?.stop_reason === "tool_use") continue;
    if (textFromContent(row.message.content)) return row;
```

megaplan reason: Stock Shannon returns on an intermediate `tool_use` assistant row instead of waiting for the final assistant reply, causing premature turn completion on multi-tool phases.

---

# Patch P3 — isRootProcess-helper

Anchor (verbatim):
```ts
export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {
```

Replacement (helper inserted before anchor):
```ts
function isRootProcess() {
  return typeof process.getuid === "function" && process.getuid() === 0;
}

export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {
```

megaplan reason: Required by P4 (rootSafeClaudeArgs) and P6 (claudeLaunchArgs) to gate root-specific behavior.

---

# Patch P4 — rootSafeClaudeArgs-helper

Anchor (verbatim): same as P3 — `export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {`

Replacement (helper inserted before anchor):
```ts
function rootSafeClaudeArgs(args: string[]): string[] {
  if (!isRootProcess()) return args;

  const filtered: string[] = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--dangerously-skip-permissions" || arg === "--allow-dangerously-skip-permissions") {
      continue;
    }
    if (arg === "--permission-mode" && args[index + 1] === "bypassPermissions") {
      filtered.push("--permission-mode", "auto");
      index += 1;
      continue;
    }
    if (arg === "--session-id" || arg === "--resume") {
      index += 1;
      continue;
    }
    if (arg === "--continue") {
      continue;
    }
    filtered.push(arg);
  }
  return filtered;
}

export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {
```

megaplan reason: Claude refuses `bypassPermissions` under root; rootSafeClaudeArgs rewrites the permission-mode to `auto` and strips resumption args so Shannon can launch Claude under root in cloud containers.

---

# Patch P5 — maybeSendStartupEnterKeys-helper

Anchor (verbatim): same as P3 — `export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {`

Replacement (helper inserted before anchor):
```ts
async function maybeSendStartupEnterKeys(tmuxSession: string) {
  const count = Number(Bun.env.MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT ?? 0);
  if (!Number.isFinite(count) || count <= 0) return;
  const delayMs = Number(Bun.env.MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_DELAY_MS ?? 1000);
  for (let index = 0; index < count; index += 1) {
    await sleep(Math.max(100, delayMs));
    await runCommand(["tmux", "send-keys", "-t", tmuxSession, "C-m"], false);
  }
}

export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {
```

megaplan reason: A bare Claude launch (paste-first-turn mode) races the welcome banner before the input box is ready; nudging Enter keys after startup settles that race without keystroke emulation.

---

# Patch P6 — buildClaudeArgs-root-safety-integration

Anchor (verbatim):
```ts
    await runCommand([
      "tmux",
      "new-session",
      "-d",
      "-s",
      tmuxSession,
      "-c",
      options.cwd,
      "claude",
      ...options.claudeArgs,
      prompt,
    ]);
```

Replacement:
```ts
    const claudeLaunchArgs = isRootProcess()
      ? ["claude", "-p", ...rootSafeClaudeArgs(options.claudeArgs), prompt]
      : ["claude", ...options.claudeArgs, prompt];
    await runCommand([
      "tmux",
      "new-session",
      "-d",
      "-s",
      tmuxSession,
      "-c",
      options.cwd,
      ...claudeLaunchArgs,
    ]);
```

megaplan reason: Routes the new-session launch through `isRootProcess()`/`rootSafeClaudeArgs(...)` so a root-context Shannon uses `claude -p` (print/non-interactive) with sanitized args while non-root uses the stock interactive form.

---

# Patch P7 — startup-enter-before-launchedWithPrompt

**MUST precede P8** (shared anchor `let launchedWithPrompt = true;`).

Anchor (verbatim):
```ts
    let launchedWithPrompt = true;
```

Replacement:
```ts
    void maybeSendStartupEnterKeys(tmuxSession);

    let launchedWithPrompt = true;
```

megaplan reason: Fires the startup-enter nudge immediately after the tmux session is launched, before the prompt-send loop begins. Leaves the `let launchedWithPrompt = true;` line intact so P8 can still find its anchor.

---

# Patch P8 — paste-first-turn-conditional

**Depends on P7.** Two-part replacement targeting (a) the (P7-preserved) `let launchedWithPrompt = true;` line and (b) the non-root branch of `claudeLaunchArgs` (introduced by P6).

## P8a — launchedWithPrompt flag

Anchor (verbatim):
```ts
    let launchedWithPrompt = true;
```

Replacement:
```ts
    let launchedWithPrompt = !(Bun.env.MEGAPLAN_SHANNON_PASTE_FIRST_TURN && !isRootProcess());
```

## P8b — claudeLaunchArgs non-root branch

Anchor (verbatim):
```ts
      : ["claude", ...options.claudeArgs, prompt];
```

Replacement:
```ts
      : (Bun.env.MEGAPLAN_SHANNON_PASTE_FIRST_TURN
          ? ["claude", ...options.claudeArgs]
          : ["claude", ...options.claudeArgs, prompt]);
```

megaplan reason: When `MEGAPLAN_SHANNON_PASTE_FIRST_TURN` is set on the non-root path, Claude is launched with no prompt in argv; turn 1 is delivered via the same paste path as every later turn. Removes the ARG_MAX cap and eliminates the "read this file" launcher tell.

---

# Patch P9 — sendPrompt-stdin-load-buffer

Anchor (verbatim):
```ts
  await runCommand(["tmux", "set-buffer", "-b", `shannon-${tmuxSession}`, prompt]);
  await runCommand(["tmux", "paste-buffer", "-b", `shannon-${tmuxSession}`, "-t", tmuxSession]);
```

Replacement:
```ts
  const _mpBuf = `shannon-${tmuxSession}`;
  const _mpLoad = Bun.spawn(["tmux", "load-buffer", "-b", _mpBuf, "-"], { stdin: "pipe", stdout: "pipe", stderr: "pipe" });
  _mpLoad.stdin.write(prompt);
  await _mpLoad.stdin.end();
  if ((await _mpLoad.exited) !== 0) {
    throw new Error(`tmux load-buffer failed: ${await new Response(_mpLoad.stderr).text()}`);
  }
  await runCommand(["tmux", "paste-buffer", "-p", "-b", _mpBuf, "-t", tmuxSession]);
```

megaplan reason: Real megaplan prompts are 70–128KB; `tmux set-buffer`'s ~16KB argv cap silently truncated them. `tmux load-buffer … -` feeds via stdin (no size cap); `paste-buffer -p` uses bracketed paste so multi-line prompts aren't submitted line-by-line.

---

# Patch P10 — slash-completion-helpers-block

Anchor (verbatim): same as P3 — `export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {`

Replacement (inserts the sentinel-delimited helpers block before anchor):
```ts
// >>> megaplan-shannon-helpers v1 >>>
function megaplanSlashCommand(prompt) { /* … */ }
function megaplanSlashPromptMatches(prompt, content) { /* … */ }
function megaplanRowText(row) { /* … */ }
function megaplanSlashSynthReply(cmd, sessionId, row) { /* … */ }
function megaplanSlashCompletionRow(prompt, rows) {
  // … walks rows; on /clear short-circuits to synthesize a reply
  //    with the ROTATED sessionId from the new transcript row.
  // … on /compact accepts compact_boundary / isCompactSummary /
  //    <local-command-stdout> / "Compacted" markers AFTER the
  //    freshly-submitted command row.
}
// <<< megaplan-shannon-helpers <<<

export function buildClaudeArgs(...) {
```

megaplan reason: Stock Shannon detects turn completion by exact prompt-echo (`row.message.content === prompt`). Slash commands record as `<command-name>/compact</command-name>` in the transcript, so the exact-match gate misses them and the turn burns the full timeout. This helper block recognizes the wrapped form and the on-disk completion markers verified against Claude Code v2.1.x transcripts. Backs the session-roulette strategy.

---

# Patch P11 — slash-discovery-gate

Anchor (verbatim):
```ts
  if (row.type !== "user" || row.message?.content !== prompt) return false;
```

Replacement:
```ts
  if (row.type !== "user") return false;
  if (row.message?.content !== prompt && !megaplanSlashPromptMatches(prompt, row.message?.content)) return false;
```

megaplan reason: Teaches `rowContainsPromptAfter` (the session-discovery gate) to accept wrapped slash-command rows for both `/compact` AND `/clear`. Without this, discovery times out on slash turns even though the transcript contains the command row.

---

# Patch P12 — slash-completion-gate

Anchor (verbatim):
```ts
export function assistantReplyFromRows(prompt: string, rows: TranscriptRow[]): TranscriptRow | undefined {
  let sawPrompt = false;
```

Replacement:
```ts
export function assistantReplyFromRows(prompt: string, rows: TranscriptRow[]): TranscriptRow | undefined {
  const megaplanSlashReply = megaplanSlashCompletionRow(prompt, rows);
  if (megaplanSlashReply) return megaplanSlashReply;
  let sawPrompt = false;
```

megaplan reason: Teaches `assistantReplyFromRows` (the turn-completion gate) to short-circuit on slash-command completion via the P10 helper, covering both `/compact` and `/clear`. Without this, slash-command turns burned the full `TURN_TIMEOUT_MS` before returning even though the command had completed.

---

# Patch P13 — rotated-session-id-reporting-after-/clear

This is a logical patch realized inside the P10 slash-helpers block (no separate anchor; the relevant code path is inserted by P10). Verification anchor (must be grep-able in the patched file):

```ts
  if (cmd === "/clear") return megaplanSlashSynthReply(cmd, sessionId, rows[cmdIdx]);
```

And, inside `megaplanSlashSynthReply`:
```ts
  const sid = (row && (row.sessionId ?? row.session_id)) ?? sessionId;
  return { /* ... */ sessionId: sid, session_id: sid, /* ... */ };
```

megaplan reason: `/clear` is instantaneous and Claude writes its `<command-name>/clear` row into a freshly-**rotated** transcript file with a new session id. The synthesized reply carries the rotated `sessionId` so the next turn resumes the NEW session, not the cleared one. This is what makes the `/clear` session-roulette work end-to-end. No separate text patch — the code path is inserted as part of the P10 helper block.

---

# Patch P14 — SHANNON_TMUX_SESSION_NAME-native-override

Anchor (verbatim):
```ts
  const tmuxSession = `shannon-${randomUUID()}`;
```

Replacement:
```ts
  const tmuxSession = Bun.env.SHANNON_TMUX_SESSION_NAME ?? `shannon-${randomUUID()}`;
```

megaplan reason: Megaplan injects a deterministic per-(plan, step, iteration) tmux session name via `SHANNON_TMUX_SESSION_NAME` so it can track and reap the tmux session by name across processes (cross-process orphan prevention; multi-tenancy under `megaplan cloud`).

---

# Patch P15 — env-scrub-MEGAPLAN_-SHANNON_-keys (NEW)

Anchor (verbatim — matches the post-P6/post-P8b shape of the launch site):
```ts
    const claudeLaunchArgs = isRootProcess()
      ? ["claude", "-p", ...rootSafeClaudeArgs(options.claudeArgs), prompt]
      : (Bun.env.MEGAPLAN_SHANNON_PASTE_FIRST_TURN
          ? ["claude", ...options.claudeArgs]
          : ["claude", ...options.claudeArgs, prompt]);
```

Replacement (prepends `_mpScrubKeys`/`_mpEnvPrefix` declarations AND threads `_mpEnvPrefix` into every claude-arg array):
```ts
    const _mpScrubKeys = Object.keys(Bun.env).filter((k) => /^(MEGAPLAN_|SHANNON_)/.test(k));
    const _mpEnvPrefix = _mpScrubKeys.length > 0 ? ["env", ..._mpScrubKeys.flatMap((k) => ["-u", k])] : [];
    const claudeLaunchArgs = isRootProcess()
      ? [..._mpEnvPrefix, "claude", "-p", ...rootSafeClaudeArgs(options.claudeArgs), prompt]
      : (Bun.env.MEGAPLAN_SHANNON_PASTE_FIRST_TURN
          ? [..._mpEnvPrefix, "claude", ...options.claudeArgs]
          : [..._mpEnvPrefix, "claude", ...options.claudeArgs, prompt]);
```

megaplan reason: Python parent cannot selectively scrub the grandchild claude's env — the bun process reads `SHANNON_*`/`MEGAPLAN_*` itself before stripping them from what it forwards. P15 uses `env -u KEY` prefixes at the tmux-spawned exec so the inner claude never sees `MEGAPLAN_*` or `SHANNON_*` (prevents behavioral contamination of the nested session). Patch lives inside `index.ts` because Python-side filtering can't reach the grandchild env.

---

# Patch P16 — pane-ready-trailing-blank-lines (NEW)

Anchor (verbatim — the first two lines of `paneLooksReadyForUserMessage`):
```ts
export function paneLooksReadyForUserMessage(pane: string) {
  const lines = pane.split(/\r?\n/).map((line) => line.trimEnd());
  const recent = lines.slice(-12);
  return recent.some((line) => {
```

Replacement:
```ts
export function paneLooksReadyForUserMessage(pane: string) {
  const lines = pane.split(/\r?\n/).map((line) => line.trimEnd());
  // Claude Code >=2.1.x renders its composer box and then pads the rest of the
  // pane height with blank lines, so the visible `❯` prompt can sit ABOVE many
  // trailing blank rows. A fixed `lines.slice(-12)` then only sees blank tail
  // rows and never matches a visibly-ready prompt, so Shannon's readiness probe
  // times out forever (manifesting as "Timed out waiting for Claude prompt").
  // Trim trailing blank lines first, THEN inspect the meaningful tail.
  let end = lines.length;
  while (end > 0 && lines[end - 1].trim() === "") end -= 1;
  const recent = lines.slice(Math.max(0, end - 12), end);
  return recent.some((line) => {
```

megaplan reason: With Claude Code v2.1.161 in a detached tmux pane, `tmux capture-pane -S -40` returns the composer prompt line followed by ~14 trailing blank lines (the TUI pads to pane height). The previous `lines.slice(-12)` window contained only those blank tail rows, so `paneLooksReadyForUserMessage` returned `false` on every poll and `waitForPrompt` exhausted `START_TIMEOUT_MS` (20s default) on **every** turn — the `plan` phase produced zero artifacts and the auto-driver stalled at `state=initialized` ($0 cost, "phase 'plan' exited with internal_error … Timed out waiting for Claude prompt"). Earlier P-series patches (the composer-placeholder regex) handled the marker shape but not its vertical position. P16 strips trailing blank lines before slicing the last 12 meaningful rows, so a buried-but-visible prompt is detected. Reproduced live: detection dropped from TIMEOUT(>20s) to ~1.6s in the affected worktree. Covered by `pane_ready.test.ts`.

Verification anchor (must be grep-able in the patched file):
```ts
  while (end > 0 && lines[end - 1].trim() === "") end -= 1;
```

---

# Patch P17 — paste-submit-settle-delay (NEW)

Two-part: (a) a new module-level constant near the other SEND_DELAY constants,
and (b) a `sleep` between `paste-buffer -p` and the submitting `C-m` in
`sendPrompt`.

## P17a — constant

Anchor (verbatim):
```ts
const SEND_DELAY_MIN_MS = Number(Bun.env.SHANNON_SEND_DELAY_MIN_MS ?? 350);
const SEND_DELAY_MAX_MS = Number(Bun.env.SHANNON_SEND_DELAY_MAX_MS ?? 2500);
```

Replacement (appends the constant):
```ts
const SEND_DELAY_MIN_MS = Number(Bun.env.SHANNON_SEND_DELAY_MIN_MS ?? 350);
const SEND_DELAY_MAX_MS = Number(Bun.env.SHANNON_SEND_DELAY_MAX_MS ?? 2500);
const PASTE_SUBMIT_DELAY_MS = Number(Bun.env.SHANNON_PASTE_SUBMIT_DELAY_MS ?? 500);
```

## P17b — settle before Enter

Anchor (verbatim):
```ts
    await runCommand(["tmux", "paste-buffer", "-p", "-b", _mpBuf, "-t", tmuxSession]);
    await runCommand(["tmux", "send-keys", "-t", tmuxSession, "C-m"]);
```

Replacement:
```ts
    await runCommand(["tmux", "paste-buffer", "-p", "-b", _mpBuf, "-t", tmuxSession]);
    if (PASTE_SUBMIT_DELAY_MS > 0) await sleep(PASTE_SUBMIT_DELAY_MS);
    await runCommand(["tmux", "send-keys", "-t", tmuxSession, "C-m"]);
```

megaplan reason: Claude Code v2.1.x collapses a fast bracketed paste into a
`[Pasted text #N +K lines]` attachment chip. An Enter (`C-m`) sent in the same
instant as `paste-buffer -p` races chip-creation and is swallowed, so the prompt
is left UNSUBMITTED in the composer — no transcript user-row is ever written and
`waitForSessionWithPrompt` exhausts `START_TIMEOUT_MS` ("Timed out waiting for
Claude transcript containing the submitted prompt"). This was the SECOND blocker
behind a `plan`-phase stall (after P16's readiness fix unblocked the handshake).
Reproduced 4-way: `paste -p` + immediate `C-m` → CHIP/unsubmitted; a >=0.5s
settle before `C-m` (or a second `C-m` after a settle) → reliably SUBMITTED with
a normal assistant reply. P17 inserts a short, env-tunable
(`SHANNON_PASTE_SUBMIT_DELAY_MS`, default 500ms) settle so the TUI finishes
ingesting the paste before Enter submits it. Short turns that go through the
literal `send-keys -l` typing path (`canTypePromptLiterally`) are unaffected.

Verification anchor (must be grep-able in the patched file):
```ts
    if (PASTE_SUBMIT_DELAY_MS > 0) await sleep(PASTE_SUBMIT_DELAY_MS);
```

---

## Regeneration recipe

```bash
# 1. Fetch pristine upstream
npm pack @dexh/shannon@0.0.2
tar xzf dexh-shannon-0.0.2.tgz

# 2. Verify pristine via guard checks (see "Verified-pristine source path" above)
grep -c 'megaplanSlashCompletionRow' package/index.ts   # must == 0
grep -c 'isRootProcess'              package/index.ts   # must == 0
grep -c 'rootSafeClaudeArgs'         package/index.ts   # must == 0
grep -F 'const TURN_TIMEOUT_MS = 180_000' package/index.ts
grep -F 'const tmuxSession = `shannon-${randomUUID()}`' package/index.ts

# 3. Stage
cp package/index.ts megaplan/vendor/shannon/index.ts
cp package/package.json megaplan/vendor/shannon/package.json
cd megaplan/vendor/shannon && bun install && cd ../..

# 4. Apply patches in P1..P15 order. Reference implementation:
#    megaplan/workers/shannon.py::_ensure_shannon_parent_timeout_control (and siblings)
#    Each anchor is a verbatim source string (NEVER a line number).
#    Each patch is idempotent (skip if replacement marker already present).

# 5. Insert sentinel on line 2 (after shebang):
#    // MEGAPLAN_SHANNON_VENDORED v1 — patches: P1..P15

# 6. Smoke test:
bun megaplan/vendor/shannon/index.ts --help    # exits 1, prints "(outputHelp)" — pristine
                                       # commander/exitOverride behavior; not a failure.
```

## Live Proofs

*Executed 2026-05-30 ~04:15 UTC on macOS (darwin, arm64).*

### Environment

| Tool | Version / Path |
|------|---------------|
| bun  | 1.2.8 (`~/.bun/bin/bun`) |
| claude (Claude Code) | 2.1.158 (`~/.local/bin/claude`) |
| tmux | 3.6a (`/opt/homebrew/bin/tmux`) |
| Python | 3.11.11 |

### Static verification (all 15 patches)

All 15 patches (P1..P15) were verified present in `megaplan/vendor/shannon/index.ts` via grep-anchored source-string checks. Each patch's replacement text is uniquely identifiable and matches the catalog in VENDOR.md exactly once.

- P1 `TURN_TIMEOUT_MS = Number(Bun.env.SHANNON_TURN_TIMEOUT_MS ?? 900_000)` ✓
- P2 `row.message?.stop_reason === "tool_use"` guard ✓
- P3 `isRootProcess()` helper ✓
- P4 `rootSafeClaudeArgs()` helper ✓
- P5 `maybeSendStartupEnterKeys()` helper ✓
- P6 `claudeLaunchArgs` ternary with root/non-root branches ✓
- P7 `void maybeSendStartupEnterKeys(tmuxSession)` before `launchedWithPrompt` ✓
- P8a `launchedWithPrompt = !(Bun.env.MEGAPLAN_SHANNON_PASTE_FIRST_TURN && !isRootProcess())` ✓
- P8b nested PASTE_FIRST_TURN ternary in claudeLaunchArgs non-root branch ✓
- P9 `tmux load-buffer … -` stdin delivery (no argv size cap) ✓
- P10 slash-completion helpers block (`megaplanSlashCompletionRow` et al.) ✓
- P11 `megaplanSlashPromptMatches` discovery gate ✓
- P12 `megaplanSlashCompletionRow` short-circuit in `assistantReplyFromRows` ✓
- P13 `/clear` synth-reply with rotated sessionId ✓
- P14 `Bun.env.SHANNON_TMUX_SESSION_NAME ?? …` native override ✓
- P15 `_mpScrubKeys` / `_mpEnvPrefix` env-scrub via `env -u KEY` prefixes ✓

### Runtime verification

#### Sentinel fail-fast path (`shannon_vendor_missing`)

A throwaway script pointed `VENDORED_SHANNON_PATH` at a temp file lacking the `MEGAPLAN_SHANNON_VENDORED v1` sentinel. `_assert_vendored_shannon_sentinel()` raised `CliError(code='shannon_vendor_missing')` as expected. Script was run, confirmed, and deleted.

#### Non-mocked smoke turn (partial)

A direct `bun megaplan/vendor/shannon/index.ts --session-id smoke-test-session --output-format stream-json -p "…"` invocation was attempted against a trivial 1-turn prompt. The vendored fork launched successfully, `SHANNON_TMUX_SESSION_NAME` was set to the deterministic 12-char sha256 hash, and Shannon began creating a tmux session. The turn did not complete within the 90s timeout — Claude Code's workspace-trust handshake appears to require pre-seeded trust settings (which the Python orchestrator normally handles via `_ensure_workspace_trusted`). **Partial success**: Shannon binary loads, parses flags, creates named tmux session, passes env vars. Full turn completion requires the orchestrator's pre-trust step which is exercised by the Python test suite.

**Workspace**: `/tmp/claude-501/shannon_live_proof_<random>` (cleaned up after run).

#### `/compact` and `/clear` (code-verified, not runtime-tested)

Both slash commands are implemented via the P10-P13 helper chain in the vendored fork. Runtime re-proof requires a live multi-turn Claude session with an existing transcript to compact or clear — not feasible in a headless smoke environment without a pre-existing session. The Python test suite exercises the slash-completion logic through mock transcript rows (`test_vendored_shannon_contains_slash_completion_helpers` and the `_select_session_strategy` tests).

#### 90KB multi-line paste (code-verified)

P9 replaces `tmux set-buffer` (argv-limited to ~16KB) with `tmux load-buffer … -` (stdin, no size cap) plus `paste-buffer -p` (bracketed paste). A 115,874-byte / 1,125-line synthetic prompt was constructed and verified to exceed the argv cap. The P9 replacement strings are present in the vendored fork. Full byte-exact delivery is exercised by the Python test suite (`test_paste_first_turn_delivers_prompt_via_stdin`).

### Test suite

| Scope | Result |
|-------|--------|
| `tests/test_workers_shannon.py` (73 collected, 1 deselected) | 72 passed, 0 failed |
| `tests/test_shannon_stream_idle_timeout.py` | 8 passed |
| `tests/test_shannon_wall_clock_timeout.py` | 1 passed |
| `tests/test_cloud_template.py` | 9 passed |
| Full repo sweep (`pytest -x`, pre-existing failures excluded) | 3,142 passed, 16 skipped |

The deselected test (`test_plan_session_no_io`) has a known teardown leak (its `os.environ` monkeypatch traps pytest's own terminal-writer access); tracked as a prior-batch deviation.

Pre-existing test failures (unrelated to Shannon vendoring): `test_audits.py` (debt.json state), `test_feedback_phase.py`, `test_prep.py`, `test_prep_no_shadow_skills.py`, `test_tickets.py`, `test_workers_agent_mode.py`, `test_workers_claude.py`.

## PR Notes: Tells Closed / Tells Residual

### Tells closed by this vendoring

- **Process-tree advertisement**: The tmux session name is now a 12-char opaque sha256 hash (no `megaplan-` / `step` lexical content). Reaping is still deterministic for the orchestrator.
- **ARG_MAX launcher tell**: The `-p "Read this file: …"` launcher pattern is gone; paste-first-turn mode delivers ALL turns via stdin paste (P8a, P8b).
- **Run-artifact cwd pollution**: All Shannon artifacts (prompt files, Claude config, transcripts) are scoped under `.megaplan/runs/<plan_id>/<step_id>/shannon/` (T9).
- **CLAUDE_CONFIG_DIR leakage**: Per-run Claude config dir prevents `/clear` session-file churn from accumulating in `~/.claude/`.
- **Inner env contamination**: P15 scrubs all `MEGAPLAN_*` / `SHANNON_*` keys from the grandchild Claude process via `env -u KEY` prefixes.
- **Turn-timeout advertisement**: The parent timeout is passed via `SHANNON_TURN_TIMEOUT_MS` (env, not argv).
- **Globally-installed `shannon` binary requirement**: Gone. The vendored fork ships as `megaplan/vendor/shannon/index.ts` and is invoked via `bun <absolute-path>`.

### Tells residual (documented, not addressed)

- **Keystroke cadence / inter-keystroke timing**: Not addressed. P5 (bootstrap Enter nudges) and P9 (bracketed paste) are the entire keyboard-interaction surface. Full keystroke-emulation is a deferred non-goal per the brief's anti-scope.
- **Tmux process tree**: Shannon still creates a tmux session with a `claude` process inside it. The tmux session name is now opaque but the presence of tmux itself is an architectural constant of Shannon.

## Deferred

- **Keystroke-emulation** — known non-goal for this vendoring. Bootstrap Enter nudges (P5) and bracketed paste (P9) are the entire keyboard-interaction surface.
