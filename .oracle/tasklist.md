# Tasklist v1 (PROPOSED — freezes only after pre-execution contract review) — plan v3

Model declaration: USER-PINNED ox-alpha for every class. No [XHARD] classifications proposed
(no task meets the exceptional threshold; all are decomposable, locally-validatable work).
Huge run: NO → no cumulative boundaries.
Sync authorization: commits land on onboard-oracle only; push restricted to origin/onboard-oracle at completion. NEVER main / native/build-forward-epic.

## Batch 1 — Detection foundation
Tasks:
1. `agentbox/onboarding/__init__.py` + `catalog.py`: provider table {id -> envKeys, default
   model/route, auth kinds, rank} ranked deepseek, openrouter, xai, anthropic, kimi-code, zai,
   moonshot, fireworks, openai-codex, grok, then catalog remainder. Parity test vs
   arnold_pipelines/megaplan/workers/omp.py `_OMP_CREDENTIAL_ENV` / `_OMP_CATALOG_MODELS`
   expectations (read-only import of worker tables where possible). [W1/R5]
2. `detect.py` adapters: foreign CLI stores (~/.codex/auth.json parseable check,
   ~/.grok/auth.json, kimi dir, claude/hermes key material); env/.env sweep; read-only agent.db
   sweep (SELECT on auth_credentials via sqlite3, PI_CODING_AGENT_DIR-aware path resolution);
   existing models.yml parse. Output ScanReport JSON, secret-free.
Checkpoint B1: adapters unit-tested incl. unreadable-file skip + secret redaction audit;
parity test green. Aligns: detect-first principle; anti-pattern blank-menu avoided.

## Batch 2 — Wiring + verification
Tasks:
1. Pin CLIProxyAPI JSON schema empirically: read fork parser fields for anthropic/openrouter/
   deepseek types + one `omp auth-broker import --dry-run --json` probe in an isolated
   PI_CODING_AGENT_DIR sandbox. [R6]
2. `wire.py`: api_key route = temp 0600 JSON file + subprocess import; oauth route = spawn
   `omp auth-broker login <provider>` inheriting TTY; cli_proxy route = models.yml YAML merge
   (preserve unknown fields/other providers, atomic os.replace, $HOME expanded at generation)
   + grok-token.py copy when wiring grok. [edge #6,#7]
3. verify wrapper in wire.py: `omp -p --no-session --model <route> "hi"`, timeout, redacted
   truncated output, pass/fail+latency.
Checkpoint B2: integration tests against REAL omp in isolated PI_CODING_AGENT_DIR/HOME tmpdir;
merge idempotence across two runs; atomicity; no hardcoded /Users paths in written files.
Aligns: persist-once, provenance recorded per stored credential.

## Batch 3 — Interactive flow
Tasks:
1. `flow.py`: guards (one-shot/resume/session-dir/non-TTY/CI/stock-omp/resident), screens 0–5,
   default-model preselected per provider, OpenRouter easy lane, loop-back-on-failed-verify,
   exit contract 0/1/2, non-TTY one-line hint, offer_and_repreflight with old-pin fallback
   (#16): FileNotFoundError/OSError on omp invocation ⇒ original failure path untouched.
Checkpoint B3: scripted-stdin session tests covering accept/decline/non-TTY/no-omp-found;
exit codes asserted. Aligns: one-verified-route success; never re-prompt afterwards.

## Batch 4 — Triggers
Tasks:
1. T1 `agentbox/arnold_agent.py` main() pre-execvp hook (guards from flow.should_offer).
2. T2 `preflight.py preflight_or_raise()` TTY menu handler → flow; non-TTY unchanged (exit 7).
3. T3 doctor --onboard flags (megaplan + agentbox doctors).
4. Golden-file test: non-TTY stderr byte-identical pre/post for declined and headless runs. [W1/R1]
Checkpoint B4: full guard-matrix tests; existing preflight/credential tests green
(tests/agentbox/test_credentials.py etc.). Aligns: fail-closed anti-pattern preserved.

## Batch 5 — Docs + validation matrix
Tasks:
1. docs/onboarding.md (UX flow, omp contract, persistence semantics) + README pointer.
2. Validation matrix: agent_goal criterion → evidence path/command/result.
3. Exact commands: `uv run pytest tests/agentbox/test_onboarding_detect.py tests/agentbox/test_onboarding_wire.py tests/agentbox/test_onboarding_flow.py tests/agentbox/test_onboarding_triggers.py -q` plus `python -m pytest tests/agentbox/test_credentials.py tests/workers/test_omp_adapter.py -q` regression subset; pty smoke E2E incl. post-flow scans: capture grepped for sk- style
   secrets [W1/R3], models.yml checked for $HOME expansion [W1/R4], persistence proof via
   second zero-prompt launch.
Checkpoint B5 (final): done criteria 1–4 of agent_goal satisfied with evidence.

## Synchronization points
B2 depends on B1 catalog/detect; B3 on B2 wire/verify; B4 composes B1–B3; B5 last. No parallel
batches except intra-batch task parallelism (B1 tasks 1–2, B4 tasks are independent files).

--- FROZEN 2026-08-25 after PASS pre-execution contract review (ContractReview). Revisions during execution go through oracle rework tasklists only. ---
