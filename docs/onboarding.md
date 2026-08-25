# First-run provider onboarding

When you launch the `arnold` custom agent on a machine with no usable inference
provider, Arnold offers a short interactive setup that finds what already exists,
wires **one** working model route, verifies it with a real call, and persists it in
oh-my-pi's own stores. After that, every later launch reuses it silently — you are
never asked the same question twice.

Implementation lives entirely on the Arnold side (`agentbox/onboarding/`); the
oh-my-pi fork is untouched. Module map:

| Module | Role |
|---|---|
| `agentbox/onboarding/guards.py` | stdlib-only launch guard (`should_offer`) |
| `agentbox/onboarding/catalog.py` | provider table: env keys, default route, auth kinds, rank |
| `agentbox/onboarding/detect.py` | read-only machine scan → `ScanReport` (secret-free) |
| `agentbox/onboarding/wire.py` | persistence into omp stores + route verification + provenance |
| `agentbox/onboarding/flow.py` | interactive screens S0–S5 and post-failure offer |

## UX flow (screens 0–5)

- **S0 — header + scan.** Read-only scan of foreign CLI stores (`~/.codex/auth.json`,
  `~/.grok/auth.json`, kimi dir), environment / omp-loaded `.env` files, omp's
  `agent.db` `auth_credentials`, and `<agent-dir>/models.yml`. Only *presence* and
  origin descriptors are read; secret values never leave detection.
- **S1 — bucketed menu (detect before asking).** Providers are listed found-first:
  `ready` (usable as-is) → `found` (detected elsewhere, needs one step to wire) →
  `missing` (hidden behind `s`). The top entry is marked `<- recommended`; OpenRouter
  is always reachable via `o` as the one-key easy path.
- **S2 — wire.** Per provider auth kind: paste an API key (input hidden; Enter cancels),
  run an OAuth login in your terminal, or reference a foreign CLI's own store
  (grok CLI proxy).
- **S3 — model pick.** The provider's default model is preselected; press Enter to keep
  it or type another `provider/model` route.
- **S4 — verify.** A real smoke call (`omp -p --no-session --model <route> "hi"`,
  90 s timeout) confirms the route works before anything is called success. On failure
  the flow loops back into that provider's menu (max 3 attempts) or lets you pick a
  different provider — it never exits half-wired.
- **S5 — success.** Shows the verified route, where it was saved, and the provenance
  ledger path; then offers (default No) to configure another provider.

Exit contract: `0` at least one verified route · `1` cancelled/declined (nothing
marked verified) · `2` non-TTY (prints one hint line).

## Trigger surfaces

All offers are TTY-gated by `guards.should_offer` — stdin AND stderr must be TTYs,
and none of: `--message` mode, `-c`, `-r`, `--resume`, `--session-dir`, `CI` set,
`ARNOLD_STOCK_OMP=1`, `MEGAPLAN_RESIDENT_MODE` set.

1. **`arnold` launch** (primary): `agentbox/arnold_agent.py` evaluates the guard
   before exec; if no ready route exists it offers the flow, then re-checks readiness.
   Onboarding code can never break a launch — any exception proceeds silently.
2. **Megaplan local-launch preflight**: when credential preflight fails on a TTY,
   the menu's sign-in option hands the terminal to `flow.run_flow`. The flow persists
   into omp's own stores — never this process's environment — so readiness is then
   re-checked from the read-only scan (`detect.scan_providers`): when every
   previously-missing slot's provider reports `ready`, the launch continues; otherwise
   the original exit-7 path runs unchanged. Non-TTY branch is untouched.
3. **`doctor --onboard`**: both `agentbox doctor --onboard` and
   `python -m arnold_pipelines.megaplan observability doctor --onboard` run the flow
   directly and report its exit code.

## Persistence semantics: persist-once, never re-prompt

Everything accepted during onboarding lands in **omp's own stores** under the agent dir
(`~/.omp/agent`, override with `PI_CODING_AGENT_DIR`) — there is no Arnold-private
credential store and no env-var-only option:

- Static API keys → `agent.db` `auth_credentials` via `omp auth-broker import`
  (providers with a CLIProxyAPI type mapping: anthropic, openai-codex), or a static
  `apiKey` entry in `models.yml` for everyone else.
- OAuth logins → `omp auth-broker login <provider>` inheriting your terminal.
- Foreign-CLI routes (grok) → a command-backed `apiKey` in `models.yml` pointing at a
  copied `grok-token.py` helper that reads the CLI's own live token at call time —
  rotating tokens are referenced live, never copied.

Later launches re-run only the cheap read-only scan. Any `ready` route suppresses the
offer entirely, so configured machines are never nagged.

### omp contract details

- **`omp auth-broker import`**: Arnold writes a CLIProxyAPI-shaped JSON tempfile
  (mode 0600, deleted afterwards) with `type`/`access_token`/`refresh_token`/`expired`.
  Because the importer requires a refresh token, static keys are stored with a synthetic
  non-secret placeholder (`arnold-static-no-refresh`) and ~10-year expiry so omp treats
  them as long-lived bearer tokens. Child processes are pinned to the agent dir via
  `PI_CODING_AGENT_DIR`.
- **`models.yml` merge (merge-don't-clobber)**: one provider block is spliced textually;
  all other bytes — comments, unknown fields, other providers — are preserved exactly.
  Writes are atomic (`os.replace` in the destination directory) and `$HOME` is expanded
  at generation time (no hardcoded `/Users/...` paths land in the file). Re-running is
  idempotent. The read-modify-write section runs under a cross-process `fcntl.flock`
  on `<agent-dir>/.models.yml.lock`, so concurrent first-run launches cannot drop each
  other's provider block.
- **Provenance ledger**: each verified wiring appends a secret-free JSON row to
  `<agent-dir>/.arnold_onboarding_provenance.jsonl`
  (`{ts, provider, mechanism, origin_kind, origin_detail, route}`) so a later failure
  can name its origin ("onboarded from ~/.codex/auth.json").

## Secrets hygiene

Detection stores presence + origin descriptors only. Pasted keys are read with echo
disabled, threaded into verification redaction as explicit known values, and never
echoed in failure details. All subprocess output that reaches the screen or logs passes
a redaction pass covering the real key shapes (`sk-*` including `sk-ant-api03-`,
`sk-proj-`, `sk-or-v1-`, plus `xai-*`) and any explicitly passed secret values. Nothing
secret is ever written to receipts, evidence files, or the provenance ledger.

## Non-TTY fail-closed guarantee

Non-TTY contexts (cloud chains, watchdogs, RPC, CI, scripted stdin) are excluded by the
guard and behave byte-for-byte as before: `run_flow` prints one hint line and exits 2,
the megaplan preflight keeps its structured stderr and exit 7, and the `arnold` launcher
falls through without printing anything extra. Declined offers take the identical typed
failure paths as today.
