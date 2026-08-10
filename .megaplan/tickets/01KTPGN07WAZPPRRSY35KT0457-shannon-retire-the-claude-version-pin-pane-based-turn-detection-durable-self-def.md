---
id: 01KTPGN07WAZPPRRSY35KT0457
title: 'Shannon: retire the claude version-pin — pane-based turn detection (durable)
  + self-defending version guard (interim)'
status: open
source: human
tags:
- bug
- shannon
- tech-debt
- refactor
- reliability
codebase_id: null
created_at: '2026-06-09T15:40:07.292718+00:00'
last_edited_at: '2026-06-09T15:40:07.292718+00:00'
epics: []
---

## Problem
vendor=claude phases driven via vendored Shannon depend on reading Claude Code's
`<sessionId>.jsonl` transcript to confirm prompt receipt and turn completion
(`waitForSessionWithPrompt` index.ts:1053 -> `rowContainsPromptAfter` :1090 ->
`readTranscript` :1301). A recurring Claude Code data-loss regression (GitHub
anthropics/claude-code#60984; also #31610) makes Shannon's fast-exit
`claude --session-id` launches write ONLY `{"type":"ai-title"}` sidecar rows — no
user/assistant message rows — so every vendor=claude phase wedges with "Timed out
waiting for Claude transcript" and the milestone stalls at `prepped`. Confirmed bad
versions: 2.1.69/70, 2.1.144/145, 2.1.169. The messages are genuinely LOST (not
relocated — swept all of ~/.claude), so reading a new store is impossible.

This has now killed the aggressive-generalized-pipeline-migration chain TWICE in one
day: each time the pinned `~/.local/bin/claude` symlink got clobbered back to a bad
version by Claude's auto-updater (the `autoUpdates:false` setting is ignored), the
next claude turn produced ai-title-only transcripts, and the driver died via
on_failure:stop_chain. Recovery each time = re-pin 2.1.168 + delete the bad binary +
archive the stall-poisoned plan + chain-state reset + relaunch.

Full diagnosis + evidence in the sibling log ticket
`.megaplan/tickets/shannon-claude-2-1-169-transcript-regression.md`.

## Why the obvious fixes are closed
- (A) Read Claude's relocated transcript store: IMPOSSIBLE — the conversation rows are
  not persisted anywhere on bad versions; it's data loss, not a format move.
- (B) Headless `claude -p --output-format stream-json` (stdout, transcript-independent):
  technically the cleanest, version-immune fix, and Shannon already has the -p /
  stream-json plumbing (index.ts:140-143). BUT `-p`/headless is FORBIDDEN per user —
  interactive-tmux is the only allowed launch mode. Option B is OUT.

## Idea 1 (INTERIM, cheap, safe — land between milestones): self-defending version guard
In `megaplan/workers/shannon.py`, before each claude launch, run `claude --version`;
if it matches a known-bad ai-title-regression set (2.1.69, 2.1.70, 2.1.144, 2.1.145,
2.1.169 — env-overridable, e.g. MEGAPLAN_CLAUDE_BAD_VERSIONS) then:
  - if the configured good binary (default 2.1.168) exists under
    ~/.local/share/claude/versions/, AUTO-RE-PIN the ~/.local/bin/claude symlink to it
    and continue; else
  - FAIL LOUD with an actionable message (which version, which good version to install,
    how to re-pin) instead of the silent "Timed out waiting for Claude transcript" wedge
    that costs a whole milestone + a manual recovery.
~20 lines + a unit test. Converts both of today's silent mid-run deaths into non-events.
Does NOT retire the pin — it makes the pin self-healing.

## Idea 2 (DURABLE — the real fix, fits inside m7 agent-runtime work): pane-based detection
The ONLY durable option compatible with the "no -p" constraint is to stop depending on
the transcript JSONL and instead observe the genuine interactive Claude via the tmux
pane. This respects the *spirit* of the -p ban (it keeps the real interactive agent —
same system prompt / tools / behavior — and only changes HOW Shannon observes it).

Feasibility is high because Shannon ALREADY captures the pane:
  - `capturePane` / `tmux capture-pane` at index.ts:1084, 1109, 1133, 1342
  - `paneLooksReadyForUserMessage` (P16) already detects the ready `❯` composer
The only thing welded to the transcript is the receipt+output gate
(`rowContainsPromptAfter` :1090, `readTranscript` :1301). Replace it with:
  - PROMPT RECEIPT / TURN COMPLETE: detect from the pane — the composer returning to the
    ready `❯` state after the prompt was sent — reusing the existing readiness probe,
    instead of polling for a `type:"user"` JSONL row.
  - OUTPUT: for plan/execute/review the real work product is files Claude writes to DISK
    (plan JSON, code edits, review artifacts), NOT transcript prose. So Shannon needs
    receipt+completion, which the pane supplies; it does not actually need the assistant
    text from the JSONL.
Result: interactive (no -p), behavioral-fidelity-preserving, and immune to the ENTIRE
transcript data-loss bug class regardless of Claude version — which lets us retire the
version pin and the self-defending guard entirely.

### Tradeoff (be honest)
Pane-scraping is more fragile than a structured transcript — that fragility is exactly
WHY transcripts exist, and Shannon has already been bitten by it (the P16 pane-padding
fix; the recent "readiness detector missed prompts pushed out by tmux pane padding"
commit). Long outputs can also scroll out of the capture buffer. So Idea 2 is deliberate,
finicky work — not a free swap. Mitigations: rely on disk artifacts for content (don't
reconstruct prose from the pane); detect completion by composer-ready transition rather
than parsing message bodies; keep the version guard until the pane path is proven.

## Suggested sequencing
- Now: Idea 1 (self-defending guard) — small, safe, stops the bleeding.
- Idea 2's natural home is the **m7-agent-runtime-extraction** milestone of the
  aggressive-generalized-pipeline-migration chain: Shannon's launch/observe runtime is
  precisely what m7 generalizes into arnold/agent/, so reworking turn-detection there
  (pane-based, transcript-independent) folds into that extraction instead of being a
  separate disruptive change. Do NOT rewrite Shannon mid-chain.

## Refs
- Sibling diagnosis ticket: shannon-claude-2-1-169-transcript-regression.md
- anthropics/claude-code#60984 (ai-title-only JSONL, no message content), #31610 (v2.1.70)
- Constraint: `claude -p` / headless is NOT permitted (user).

