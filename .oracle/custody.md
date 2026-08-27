# Custody baseline — megado-nbf-guard-0826

- Worktree: /Users/peteromalley/Documents/Arnold-oracle-nbf (branch megado-nbf-guard-0826)
- Base SHA: f8725af516da8d4249eb0d63563c37776d80daf8 (== origin/main at 2026-08-27 ~12:10Z)
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
