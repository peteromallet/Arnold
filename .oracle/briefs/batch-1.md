# Executor brief — Batch 1 (Detection foundation)
North Star: detect-before-asking; provenance everywhere; secrets NEVER in output.
Worktree: /Users/peteromalley/Documents/Arnold-onboard-oracle (branch onboard-oracle). Python 3.11, repo uses uv.

## Task 1: agentbox/onboarding/__init__.py + catalog.py
Provider table RANK_ORDER = [deepseek, openrouter, xai, anthropic, kimi-code, zai, moonshot, fireworks, openai-codex, grok] then remaining known providers (google, moonshot..., minimax, fireworks already in rank; add google, openai, perplexity etc as tail).
Per provider: env_keys tuple (source of truth: arnold_pipelines/megaplan/workers/omp.py _OMP_CREDENTIAL_ENV ~L125-134 + cloud/preflight.py _ENV_HINTS_BY_OMP_PROVIDER L53+; for others use fork packages/catalog/src/provider-models/descriptors.ts names), default_route (e.g. deepseek/deepseek-v4-flash, grok/grok-4.6, openai-codex/gpt-5.6-sol per worker _OMP_CATALOG_MODELS ~L86-113), auth_kinds subset {env, api_key, oauth, cli_proxy} (grok=cli_proxy; openai-codex=oauth; kimi-code={api_key,oauth}? verify from worker native-routes set {openai-codex,grok,kimi-code}).
Parity TEST: import worker tables and assert every provider present in _OMP_CREDENTIAL_ENV has matching envKeys in catalog.py (and vice versa) so values cannot drift.

## Task 2: agentbox/onboarding/detect.py
ScanReport dataclass -> to_json(): {"providers":[{id,status: ready|candidate|missing, origin:{kind,detail}|null, env_keys:[...], default_route}], "rank_order":[...]}. NEVER include secret VALUES - only presence + origin descriptors.
Adapters (each returns candidate origins; all read-only):
1. foreign CLI stores: ~/.codex/auth.json exists+parses JSON -> openai-codex ready(origin cli_store); ~/.grok/auth.json -> grok ready(cli_proxy); kimi config dir (~/.kimi*) presence; claude (~/.claude/.credentials.json or keychain-unreadable -> mark unknown->candidate only if file exists); hermes (~/.hermes) presence.
2. env sweep: os.environ + .env files parsed from ~/.omp/.env, ~/.omp/agent/.env, cwd/.env (report which file won per var; precedence omp-dir > cwd? mirror omp load order: later loads override - check packages/utils/src/env.ts order at impl time; document choice).
3. agent.db sweep: sqlite3 readonly URI mode (file:...?mode=ro) on $PI_CODING_AGENT_DIR/agent.db else ~/.omp/agent/agent.db; SELECT provider,credential_type FROM auth_credentials WHERE disabled_cause IS NULL -> status ready(origin kind oauth|api_key by type).
4. models.yml parse: yaml.safe_load ~/.omp/agent/models.yml; providers w/ apiKey -> ready(origin kind cli_proxy|config).
status logic: ready if any origin resolves today (env set, db row, models.yml entry); candidate if found-but-not-wired (foreign store present but not yet referenced by omp); missing otherwise.
Unreadable file/dir anywhere -> skip silently, record nothing (never crash scan).

## Tests: tests/agentbox/test_onboarding_detect.py
- monkeypatch HOME/tmp_path isolation per repo convention; unreadable-file skip; secret redaction audit (assert no value matching sk-[A-Za-z0-9]{8,} in JSON dump); parity test (task 1); rank order assertion; .env parsing incl quotes/export prefixes.

## Constraints
- NO edits outside agentbox/onboarding/, tests/agentbox/test_onboarding_detect.py.
- No subprocess calls in B1. No network. Match repo style (typed, dataclasses, no bare subprocess - repo has AST lint test_no_bare_subprocess.py: use subprocess module import inside functions is fine per existing patterns, but B1 has none anyway).
- Run: uv run pytest tests/agentbox/test_onboarding_detect.py -q  AND  uv run pytest tests/agentbox/ -q -k "onboarding" ; report output verbatim.
- Commit NOTHING; leave worktree dirty for oracle diff.
