# Agent goal — first-run provider onboarding for the `arnold` custom agent

[North Star](./northstar.md)

## Objective
When a user launches the `arnold` custom agent (agentbox launch path) for the first time on a
machine with zero usable inference providers, Arnold offers an interactive onboarding flow that:
1. scans the machine read-only (foreign CLI stores, env/.env vars, omp agent.db, models.yml);
2. presents found routes first (bucketed ready / found-elsewhere / not-found), with OpenRouter
   surfaced as the always-visible easy path;
3. lets the user pick ONE primary provider (default model preselected per provider, changeable),
   wires it by copying static keys into omp's credential store or generating `models.yml`
   entries (rotating tokens referenced live, never copied), with explicit consent and provenance;
4. verifies the wired route with a real `omp -p --no-session --model <route>` smoke test
   (loop back into that provider's menu on failure; never exit half-wired);
5. persists everything in omp's own stores, then resumes the user's original launch intent.

## How this run advances the North Star
Implements the end state directly: first `arnold` launch to first verified model, once, with no
re-prompts afterwards.

## Authoritative inputs
- Design conversation with the user (2026-08-25): UX screens 0–5, copy-vs-reference rule,
  persistence model, edge cases #1–#16 (esp. merge-don't-clobber models.yml (#6), $HOME
  expansion not hardcoded paths (#7), old-pin command-not-found fallback (#16)).
- Existing research: fork surfaces (auth-broker import CLIProxyAPI parser, AuthStorage cascade,
  setup-wizard) and Arnold surfaces (_OMP_CREDENTIAL_ENV workers/omp.py:86–134,
  _ENV_HINTS_BY_OMP_PROVIDER cloud/preflight.py:53, _check_required_credentials
  agentbox_adapter.py:982, branded binary resolution agentbox/arnold_agent.py).

## In scope
- Arnold-side Python module(s): detection adapters, interactive offer/wiring/verify flow,
  persistence via ~/.omp/agent/models.yml generation + omp CLI mechanisms available WITHOUT
  fork changes (e.g. `omp auth-broker import` for CLIProxyAPI JSON, omp's native login where a
  CLI exists).
- Trigger wiring: `arnold` agentbox launch path (primary trigger), megaplan local launch
  preflight failure paths, `doctor` (--onboard flag). TTY-gated offers only.
- Targeted pytest coverage for: detection adapters, models.yml merge semantics, non-TTY
  fail-closed behavior, old-pin fallback, offer helper.
- Docs: short onboarding section describing the flow + omp contract.

## Non-goals
- ANY change to ~/Documents/oh-my-pi unless a capability is PROVEN impossible from Arnold side
  (record evidence first; ask user before touching the fork).
- Cloud/agentbox/watchdog headless behavior changes beyond preserving them.
- New credential storage formats, broker deployment, multi-machine sync.
- Provider catalog expansion beyond what omp already supports.

## Settled decisions (from user)
- Implementation lives in the ARNOLD repo ideally; oh-my-pi fork only if impossible.
- Flow fires when launching the `arnold` CUSTOM AGENT first time.
- Persist everything at onboarding; reuse silently afterwards; no env-var-only option —
  static keys are copied into omp stores by default.
- ox-alpha performs every role this run (planner/explorer/executor/oracle); vigorous testing
  at completion.

## Authorization boundaries
- Mutate: only this worktree (branch onboard-oracle). Commit after each batch.
- Sync/push: push branch `onboard-oracle` to origin at completion. NEVER main,
  NEVER native/build-forward-epic. No deploy/promotion.
- Secrets: never printed, logged, or stored in receipts/artifacts.

## Done criteria
1. Fresh-launch simulation (empty credential env + clean agent dir) triggers the offer on a
   TTY and completes to one verified route; declined/non-TTY paths produce today's typed
   failure unchanged.
2. Wired route survives a NEW process (persistence proof): second launch runs with zero prompts.
3. All targeted tests pass; full affected test subset green.
4. Every agent-goal criterion mapped to evidence; North Star disposition recorded.

## Validation commands
- Targeted: `uv run pytest tests/... -k onboard` (paths fixed in tasklist)
- Smoke (real machine): scripted pty session exercising screens 0–5; verify exit codes 0/1/2
  contract; models.yml merge idempotence across two runs.
- Full-suite subset: existing preflight/credential-related tests still green.

## Stop conditions
blocked / failed / undetermined / retryable / escalate per skill contract; escalate any
proposed fork change to the user before implementing.
