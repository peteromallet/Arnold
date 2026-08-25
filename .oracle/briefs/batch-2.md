# Executor brief — Batch 2 (Wiring + verification)
North Star: persist-once in omp's own stores; consent-gated; provenance recorded; secrets never printed/logged.
Worktree: /Users/peteromalley/Documents/Arnold-onboard-oracle (branch onboard-oracle). Commit NOTHING.

## Task 1: Pin CLIProxyAPI JSON schema empirically
Read fork parser: ~/Documents/oh-my-pi/packages/coding-agent/src/cli/auth-broker-cli.ts runImport (~L565) + CLIPROXY_TYPE_TO_PROVIDER (~L430) to get exact field names per credential type (anthropic, openai, codex...). Then EMPIRICALLY verify with an isolated sandbox:
  export PI_CODING_AGENT_DIR=$(mktemp -d) ; omp auth-broker import --help
Write a dummy JSON file for type=openai with a FAKE key and run `omp auth-broker import <file> --json` against the isolated dir; inspect the sqlite db to confirm the row shape. NEVER touch ~/.omp/agent/agent.db in tests. Record exact schema in agentbox/onboarding/wire.py docstring.

## Task 2: wire.py
- wire_api_key(provider_id, api_key, *, agent_dir) -> WireResult:
    build CLIProxyAPI JSON {type: mapped, ...fields per parser} in tempfile (mode 0600),
    subprocess.run(["omp","auth-broker","import",path,"--json"], capture, timeout=120,
    env={**os.environ, "PI_CODING_AGENT_DIR": str(agent_dir)}); delete tempfile in finally;
    parse stdout JSON for success; return WireResult(ok, provider, mechanism="auth-broker-import", provenance).
  Provider->CLIProxyAPI type map lives here; providers without a mapping fall back to models.yml route.
- wire_oauth(provider_id, *, agent_dir): subprocess.run(["omp","auth-broker","login",provider_id]) INHERITING stdio (interactive), timeout=None but guard non-TTY -> raise/skip.
- wire_cli_proxy(provider_id, source, *, agent_dir): grok-style — merge entry into models.yml:
    load existing yaml.safe_load (or {}), preserve unknown fields/other providers verbatim,
    set providers[<id>].apiKey = f"!{cmd}" where cmd uses EXPANDED absolute paths (no ~ literals? use expanded $HOME path),
    atomic write via os.replace of tmp file in same dir, file mode preserved/0600.
    For grok: copy docs template script (reimplement minimal version inline as data or copy from fork docs/omp-setup/grok-token.py content) to agent_dir/grok-token.py chmod +x.
- record_provenance(agent_dir, entries): append JSONL to agent_dir/.arnold_onboarding_provenance.jsonl {ts, provider, mechanism, origin_kind, origin_detail} — no secrets.

## Task 3: verify wrapper (in wire.py)
verify_route(route, *, agent_dir, timeout=90) -> VerifyResult(ok, latency_ms, redacted_output):
  subprocess.run(["omp","-p","--no-session","--model",route,"hi"], env with PI_CODING_AGENT_DIR,
  capture_output=True, text, timeout). Redaction: replace any sk-[A-Za-z0-9]{8,} and the actual
  key values if passed in; truncate output to 200 chars. Never raise on nonzero exit -> ok=False.

## Tests: tests/agentbox/test_onboarding_wire.py (isolated PI_CODING_AGENT_DIR/tmp HOME)
- import round-trip into REAL omp sandbox dir: assert auth_credentials row exists (sqlite read).
- fake-key E2E only against sandbox; mark network-touching verify test to skip unless RUN_OMP_VERIFY=1 env set.
- models.yml merge: existing user content preserved byte-wise except added provider; idempotent second run (no dup keys); atomicity (no partial file on simulated crash is hard—assert os.replace usage by monkeypatching); $HOME expansion assertion (no '/Users/' literals written except real home).
- provenance JSONL appended, secret-free.
- subprocess calls all go through a small _run() helper so tests can monkeypatch it (repo bans bare subprocess outside runtime — check tests/test_no_bare_subprocess.py rules! If it scans agentbox/, ensure compliance: likely requires using a wrapper or allowed module list. READ that test first and comply).

Run: uv run pytest tests/agentbox/test_onboarding_wire.py -q AND uv run pytest tests/agentbox -q -k onboarding.
Report: files, verbatim pytest output, empirical import schema findings, deviations.
