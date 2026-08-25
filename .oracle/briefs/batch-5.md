# Batch 5 — Docs + validation matrix (from tasklist v3, Batch 5)

## Tasks
1. docs/onboarding.md (UX flow screens 0–5, omp contract: auth-broker import/login,
   models.yml merge, provenance ledger; persistence semantics: persist-once, never
   re-prompt; trigger surfaces: arnold launch, megaplan preflight TTY menu,
   doctor --onboard; non-TTY fail-closed guarantee) + minimal README pointer.
2. Validation matrix at .oracle/evidence/validation-matrix.md mapping EVERY agent_goal
   done criterion + North Star principle to evidence paths/commands/results.
3. Full validation battery with captured outputs under .oracle/evidence/:
   a. uv run pytest tests/agentbox -q -k onboarding
   b. uv run pytest tests/test_pipeline_run_cli.py tests/characterization tests/agentbox/test_arnold_agent.py tests/agentbox/test_credentials.py -q
   c. E2E secret scan [W1/R3]: scripted flow session with fake key; grep full captured
      transcript for key value and sk- patterns → absent.
   d. $HOME check [W1/R4]: wire_cli_proxy sandbox models.yml contains no '/Users/' paths
      other than the real expanded home.
   e. Persistence proof: two consecutive scripted launches in same sandbox — second shows
      no prompt (offer skipped because ready route exists).

## Checkpoint B5 (final): done criteria 1–4 of agent_goal satisfied with evidence.

## Constraints
- Do NOT commit anything; leave tree dirty for final oracle review.
- Secrets never printed/logged/stored in receipts/artifacts.
