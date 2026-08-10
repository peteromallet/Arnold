# B1 — Baseline manifest, census, and frozen omp provider contract

Executed 2026-08-10 against the executable to-do list `docs/omp-replaces-hermes-todo.md`.

## 1. Baseline manifest

| Item | Value |
|---|---|
| `git rev-parse HEAD` | `9efd9c2aa7a7998c230180d172a67153dadc3254` |
| `git status --short` | (empty — clean tree) |
| `git diff --name-only` | (empty) |
| `git diff --check` | clean |

No existing dirty paths to preserve or classify. The tree is clean at the recorded HEAD.

Workspace reality vs. the todo's macOS paths: the Arnold checkout lives at
`/workspace/omp-replaces-hermes/Arnold`, the omp fork at
`/workspace/omp-replaces-hermes/oh-my-pi` (editable copy; **no `.git` directory** —
B5's fork-diff gate requires initializing a git repo there and comparing against
the upstream omp head), and Astrid at `/workspace/omp-replaces-hermes/Astrid`
(also no `.git`). All omp-rpc sources are present under
`oh-my-pi/python/omp-rpc`.

## 2. Census

Full per-line listing: `docs/b1-census-full.txt` (1756 hits, 268 files).

Pattern breakdown (repo roots: `arnold arnold_pipelines agentbox tests .github pyproject.toml .env.example`):

| Pattern | Hits |
|---|---|
| `hermes:` | 641 |
| `arnold\.agent` | 619 |
| `\.hermes` | 304 |
| `AIAgent` | 165 |
| `run_agent` | 102 |
| `launch_hermes` | 51 |
| `DeepSeekAdapter` | 33 |
| `hermes_auth` | 0 |

Top clusters by file:

- `arnold/agent/**` (run_agent.py 98, model_tools.py 34, adapters/deepseek.py 27, auxiliary_client.py 18, hermes_cli/config.py 15, providers/, tools/, cron/, honcho_integration/) — the Hermes agent SDK. **Live deletion target (B11).**
- `arnold_pipelines/megaplan/workers/hermes.py` (33) — **live, replaced by `workers/omp.py` (B2), deleted (B11).**
- `arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py` (43), `fan.py` (23) — **live, migrated (B4/B8/B11).**
- `arnold_pipelines/megaplan/profiles/*.toml` (partnered-3/4/5, solo, etc.) — **live, migrated (B4).**
- `arnold_pipelines/megaplan/workers/_impl.py` (15) — **live, dispatch threading (B3).**
- `arnold_pipelines/megaplan/runtime/sandbox.py` + `key_pool.py` — re-export from `arnold.agent.tools.sandbox` / `arnold.agent.providers.pool`; **live, vendored in B11** (the only `arnold.agent` import edge remaining after B11's deletion).
- `arnold/conformance/_allowlist.txt` (49), `arnold/security/coverage_matrix.py` (30), `arnold/conformance/checks.py` (15) — conformance/security inventory of the old SDK; deleted with the SDK or rewritten to the neutral runtime (B11).
- `tests/**` (test_profile_policy.py 35, test_worker_concurrency.py 30, test_fallback_chains_profile_validation.py 28, test_deepseek_adapter.py 24, test_arnold_dispatcher.py 18, fixtures/critique_ledger/m6-corpus.json 114) — **live tests, rewritten/migrated across B2–B12**; fixtures retained as historical evidence where they are not load-bearing.
- `.megaplan/**`, docs archive, SOL/design/review artifacts — **historical / explicitly permitted transitional** (B13 allowlist).

`hermes_auth`: zero hits — no auth-state surface exists under that name in the census roots.

Additional surfaces named by the contract: `_compatibility.py` `--hermes`/`--phase-model` handling and `cloud/summarize_fixer_session.py` launcher assumptions are both present and live; both are migrated in B3/B9.

## 3. Frozen omp provider contract

Verified against the real catalog (`oh-my-pi/packages/catalog/src/models.json`, host descriptors in `provider-models/descriptors.ts`), the RPC client (`python/omp-rpc/src/omp_rpc/`), and `model-thinking.ts`.

Grammar: exactly `omp:<provider/modelId>`. Arnold-side effort suffix is stored separately and becomes `--thinking <level>` / `RpcClient(thinking=...)`. `omp:provider:model` (double-colon) is never emitted.

| Route | Canonical catalog model | Credential env var(s) | Catalog verified |
|---|---|---|---|
| DeepSeek | `deepseek/deepseek-v4-pro` or `deepseek/deepseek-v4-flash` | `DEEPSEEK_API_KEY` | yes (api=openai-completions, reasoning=True) |
| Fireworks | `fireworks/kimi-k2.7-code` | `FIREWORKS_API_KEY` | yes |
| zAI | `zai/glm-5.2` | `ZAI_API_KEY` (legacy `ZHIPU_API_KEY` alias) | yes (api=anthropic-messages) |
| Moonshot | `moonshot/kimi-k2.7-code` | `MOONSHOT_API_KEY` or `KIMI_API_KEY` | yes |
| Kimi Code OAuth | `kimi-code/kimi-for-coding` | Kimi OAuth / `KIMI_API_KEY` | yes |
| OpenRouter | `openrouter/openai/gpt-5.5` (+ selected OpenRouter DeepSeek row) | `OPENROUTER_API_KEY` | yes |
| xAI | `xai/grok-4-fast-non-reasoning` | `XAI_API_KEY` | yes (reasoning=False) |
| Anthropic | `anthropic/claude-opus-4-8` | `ANTHROPIC_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` | yes (api=anthropic-messages) |

Thinking levels (RPC `protocol.py`): `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` — plus CLI-level `auto`. RPC client receives only its typed levels. Per-host maps are authoritative (`model-thinking.ts`): OpenRouter DeepSeek is high-only; Kimi K3 (Kimi Code) low/high/max; GLM-5.2 high/max; Fireworks maps `minimal` → provider `none`; remaining host-specific mappings copied exactly from `model-thinking.ts`.

No-spend validation command per row: registry/model lookup + RPC `get_state` / `set_model`; no live completion required.

Provider family = upstream provider; transport identity stays `omp`.

## 4. Gate B1 evidence

```bash
git diff --check          # clean
rg -n '<census patterns>' arnold arnold_pipelines agentbox tests .github pyproject.toml .env.example   # 1756 hits, all classified above
python -m pytest --collect-only -q
cd oh-my-pi && python3 -m pytest -q python/omp-rpc/tests
```

No unresolved verification caveat: every census hit is assigned to a live-migration batch, a deletion batch, or the B13 historical allowlist.
