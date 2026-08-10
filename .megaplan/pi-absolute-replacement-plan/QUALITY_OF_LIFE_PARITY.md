# Quality-Of-Life Parity Notes

Date: 2026-07-04

This note captures non-obvious ergonomics that operators may take for granted
in Hermes, Claude, Codex, Shannon, and the existing Megaplan skills. These are
not all hard correctness contracts, but losing them would make the unified
surface feel worse and encourage bypasses.

## QoL Contracts To Preserve Or Deliberately Replace

- **Context compaction and budget control**: automatic compaction, explicit
  context-budget knobs, warning before context exhaustion, summarized tool
  history, and clear "what was dropped" provenance.
- **Session persistence and resume**: opt-in persistent sessions, stateless
  one-shot mode, resume identifiers, history lookup, and safe "fresh session"
  behavior.
- **Liveness and hang detection**: heartbeats, process idle detection,
  wedged-stdin detection, timeout diagnostics, and partial artifact visibility
  while a run is active.
- **Prompt and large-input ergonomics**: query-file support, long-prompt
  handling, large prompt submission without terminal paste failures, and
  rendered-prompt capture for debugging.
- **Permission modes**: readable mapping from profile permissions to engine
  native modes, including Claude permission mode, Codex sandbox/writable roots,
  terminal/web/file tool exposure, and human confirmation points.
- **Auth/session reuse**: Claude subscription/OAuth behavior, Codex OAuth/API
  behavior, provider key reuse, refresh-token shims, and clear doctor output
  when a route degrades because a credential is missing.
- **Model and token defaults**: safe max-token defaults, reasoning-token
  awareness, model shortcut aliases, vendor fallback explanations, and warnings
  for empty outputs caused by length caps.
- **Streaming output**: useful live logs without raw noise, final response
  extraction, stderr/stdout separation, and compact transcript artifacts.
- **Diff/review/apply UX**: Codex review/apply style patch flow, patch-conflict
  diagnostics, review corpus quality thresholds, and easy "show me what
  changed" commands.
- **Kill and cleanup UX**: graceful vs hard kill, fanout group kill, orphan
  reaping, stale run reconciliation, and clear post-kill status.
- **Cost visibility**: live and final cost, token provenance, cost ceilings,
  per-child fanout attribution, and clear "estimated vs exact" labels.
- **Install and doctor smoothness**: one-command setup, binary/version pin
  checks, stale skill detection, config drift detection, skill/profile mismatch
  warnings, and actionable repair text.
- **Worktree ergonomics**: branch/worktree allocation, cleanup, protected
  branch checks, patch rollback, and clear ownership of temporary worktrees.
- **Skill invocation ergonomics**: skill discovery, trigger docs, preloaded skill
  content, missing-skill warnings, and Pi skill sync visibility.
- **Operator muscle memory**: existing verbs and documented runbooks keep
  working during the observation window, even if internally delegated through
  the facade.

## Plan Consequence

Add an explicit `operator-qol-parity-contract.md` in Epic 1 and make QoL parity
part of Epic 2's facade acceptance gate. The facade does not need to copy every
engine behavior exactly, but each item must be classified as:

- preserved;
- replaced by a better facade-native behavior;
- intentionally dropped with sign-off;
- blocked until an engine adapter supports it.

The migration is not ready for broad adoption if `agent ask` is technically
correct but worse than direct Claude/Codex/Hermes for everyday debugging,
resuming, killing, observing, and context management.
