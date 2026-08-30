# Custody baseline — megado-nbf-guard-0826

- Worktree: /Users/peteromalley/Documents/Arnold-oracle-nbf (branch megado-nbf-guard-0826)
- Historical base SHA: f8725af516da8d4249eb0d63563c37776d80daf8 (== origin/main at the original 2026-08-27 ~12:10Z custody capture; historical only, not the live source base)
- Source ref: origin/main; remote https://github.com/peteromallet/Arnold.git
- Base status: clean (no untracked carried)
- Other worktrees protected, must survive:
  - /Users/peteromalley/Documents/Arnold (primary checkout, branch native/build-forward-epic + untracked run docs)
  - /Users/peteromalley/Documents/Arnold-oracle (PRIOR unrelated megado run — do not touch)
- Environment identity: host mac (darwin 24.4.0, arm64); omp CLI at ~/.bun/bin/omp;
  glm-5.3-flash probed working via `openrouter/z-ai/glm-5.3-flash`; grok CLI at ~/.grok/bin/grok.
- Protected concurrent work: agentbox container `megaplan-cloud-agent-resident-only`
  runs the live NBF chain — read-only evidence only from this run unless a brief
  explicitly authorizes box mutation.

## Resume custody baseline — 2026-08-29

- Resume request: continue this Megado run in the existing worktree, building on
  current `origin/main`; user-pinned models are GPT-5.6 Luna for normal work and
  GPT-5.6 Sol for planning, oracle judgment, and any justified `[XHARD]` work.
- Pre-rebase HEAD: `004540970fa668558ad50603b7dc917127b8de33` on
  `megado-nbf-guard-0826`.
- Refreshed source ref: `origin/main` at
  `798c50619204010ed3f4297fbb57988fe9381924` after
  `git fetch origin main --prune`.
- Current immutable source base for this resumed run: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- Merge base before rebase:
  `af370f5ec62d467458e9c8d702b684e1b56ec136`.
- Five branch-only commits must survive the rebase: `2a5f21a8e0`,
  `d27b01345e`, `ac97fc5897`, `bbf4fbf53d`, `004540970f`.
- Pre-rebase untracked protected artifacts: `.oracle/briefs/evolution-entry13.md`,
  `.oracle/findings/evolution-entry13.txt`, `.oracle/nbf-hourly-loop-goal.md`.
- Execution-readiness audit found `.oracle/tasklist.md` belongs to the prior
  onboarding run (it names `agentbox/onboarding`, `onboard-oracle`, and
  `ox-alpha`) and does not implement the current NBF `agent_goal.md`; it is not
  authorized for execution and must be preserved only as foreign-run evidence.
- Other worktrees and the live agentbox workload remain protected exactly as in
  the original baseline above.
