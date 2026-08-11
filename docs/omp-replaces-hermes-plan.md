> **Authority status (T44):** Zero-authority historical planning artifact — for reference only; not live operational authority. Canonical delegation is via the megaplan CLI and the migrated wrappers.

# Replacing Hermes with oh-my-pi (omp) — plan v3 (post SOL round 2)

**Status:** Draft v3.1 — SOL round 2 complete (72/100); model-reference migration gap identified and closed below. Ready to execute P0.

## 2.5 Model-reference migration (gap closed by census)

The plan previously covered the *dispatch* surfaces only. A census (two passes: whole repo = 147+ files; live dirs = 39+ files) shows `hermes:`-family agent specs are pervasive and must be migrated in their own workstream. **Translation is a mapping, not a rename** — arnold specs carry agent prefix + provider + model + optional effort suffix; omp uses `provider/modelId`.

### Spec translation table (canonical)

| Arnold spec (today) | omp spec |
|---|---|
| `hermes:deepseek:deepseek-v4-pro` / `-flash` | `omp:deepseek/deepseek-v4-pro` / `-flash` |
| `hermes:fireworks:accounts/fireworks/models/kimi-k2p6` | `omp:fireworks/accounts/fireworks/models/kimi-k2p6` (or native kimi provider, verified in P0) |
| `hermes:glm-5.1` / `hermes:zhipu:glm-5.2` | `omp:zhipu/glm-5.2` (verify zhipu provider id) |
| `hermes:openrouter:deepseek/deepseek-r1` | `omp:openrouter/deepseek/deepseek-r1` |
| `hermes:xai:grok-4.5` | `omp:xai/grok-4.5` |
| `hermes:kimi-k2.6` | `omp:kimi/kimi-k2p6`-family (verify) |
| `claude:claude-sonnet-4-6` | keep `claude` CLI (Shannon adapter stays) OR `omp:anthropic/claude-sonnet-4-6` |
| `codex:gpt-5.4` | keep `codex` CLI (adapter stays) OR `omp:openai-codex/gpt-5.4` |
| `codex:gpt-5.5:high` | effort suffix → `AgentSpec.effort` (Arnold-side), passed as `model_reasoning_effort` to omp |

### Census categories (39+ live / 108+ historical)

**Live — must migrate:** `profiles/*.toml` (all-deepseek-{flash,pro,pro-direct}, all-fireworks-deepseek, all-open, apex tier_models, arnold-openrouter — every spec), `profiles/policy.py` (`CANONICAL_PREP_MODELS`→`DIRECT_DEEPSEEK_V4_PRO_SPEC`, `DEFAULT_DEEPSEEK_PROVIDER="direct"`, `DEFAULT_AGENT_ROUTING`), `arnold/agent/routing.py` (`DEFAULT_MANAGED_AGENT_MODELS`), `resident/config.py` (provider default `"hermes"`, model default `"zhipu:glm-5.2"`), `pipelines/live_supervisor/steps.py` (`_EXECUTE_TIER_MODELS`), `megaplan/runtime/key_pool.py` (resolve_model provider prefixes), `cloud/preflight.py:199-209` (hermes provider→env-hint parser), `audits/critique_evaluator.py:83-133` (hermes model-name normalizer), `cloud/wrappers/arnold-watchdog:1563` (`--model hermes:deepseek:deepseek-v4-flash`), `auto.py:7551` + `orchestration/tiebreaker.py:254` (help-text examples), `.env.example:16-18` (xai prefix docs), `data/*_skill.md` + `_composed/*` (babysit/superfixer/superpom skills pin `hermes:deepseek:deepseek-v4-flash` observers), root `AGENTS.md` (profiles + fallback examples), `agentbox/systemd/agentbox-discord-resident.service` (env defaults), `megaplan/prompts/*` (any embedded specs).

**Historical — classify, don't translate:** `.megaplan/**` briefs/evidence/research/initiatives reference specs as plan records; acceptance scan must distinguish live (fail on hit) from historical (allow, classified).

### Credential env mapping (closed from key_pool.py + omp help-extra.ts)

| Arnold key_pool provider | Arnold env | omp provider | omp env |
|---|---|---|---|
| deepseek (incl. `direct`) | `DEEPSEEK_API_KEY` | `deepseek` | `DEEPSEEK_API_KEY` |
| zhipu / glm | `ZHIPU_API_KEY` | `zai` (z.ai/GLM) | `ZAI_API_KEY` ⚠ env-name differs — translation required |
| xai | `XAI_API_KEY` | `xai` | `XAI_API_KEY` |
| openrouter | `OPENROUTER_API_KEY` | `openrouter` | `OPENROUTER_API_KEY` |
| fireworks | `FIREWORKS_API_KEY` (deepseek-via-fireworks falls back to `DEEPSEEK_API_KEY`) | `fireworks`? | ⚠ P0: provider + env presence unverified |
| kimi | `KIMI_API_KEY`/`MOONSHOT_API_KEY` | `kimi`? (or openrouter route) | ⚠ P0: provider presence unverified |
| anthropic | `ANTHROPIC_API_KEY` | `anthropic` | `ANTHROPIC_API_KEY` |
| codex | `OPENAI_API_KEY` | `openai-codex` | `OPENAI_API_KEY` |

`hermes:deepseek:…` via the `direct` provider = omp's native `deepseek` provider (direct API). The `preflight.py` `_ENV_HINTS_BY_HERMES_PROVIDER` parser and `key_pool.py` resolve_model table must be replaced by one omp-side mapping; the adapter/translation layer owns the env-name translation (`ZHIPU_API_KEY` → `ZAI_API_KEY`).

### Deliverables (P0/P1)

1. **P0: omp provider registry check** — verify omp providers exist for deepseek/fireworks/zhipu/openrouter/xai/kimi/anthropic/openai-codex; produce the final translation table (incl. the ⚠ rows above).
2. **P0: parser updates** — `preflight.py` env-hint extraction and `critique_evaluator.py` normalizer learn `omp:` (or delegate model resolution to omp entirely).
3. **P1: defaults+profiles migration** — policy.py, routing.py, resident config, live_supervisor tiers, all profiles/*.toml, service unit env, .env.example, wrapper argv, skills, AGENTS.md.
4. **P2: acceptance scan** — `rg "hermes:"` over live dirs → zero; historical classified.
**Goal (user-stated):** (1) omp replaces **all** Hermes usage in Arnold; (2) omp becomes the **resident-agent platform** — anyone can create a domain resident agent (example: Astrid) with the Arnold resident pattern; (3) the **omp fork stays reasonably clean** — platform ships via user/project `.omp/` config, examples, and one tooling script; zero `src/` changes.

Artifacts: SOL r1 `/tmp/sol-review-1.md`, SOL r2 `/tmp/sol-review-2.md`; 13 scout artifacts listed in Appendix. This file is the plan of record.

---

## 1. Confirmed architecture facts (13 scouts + 2 SOL passes)

1. **One dispatch table** — every phase (prep/plan/critique/revise/gate/finalize/execute/review + loop_* + tiebreaker_* + feedback/critique_evaluator) converges on `run_step_with_worker` → branch table `workers/_impl.py:7519-7658` (hermes/claude/shannon/codex only; `omp` hits a hard assert on empty `resolved_model` `:7552-7556`). `parse_agent_spec` **already accepts arbitrary tokens** (`omp:<model>` works today). `_is_agent_available:6599` special-cases hermes only; dispatcher flag-ON hard-codes `DeepSeekAdapter` `:7663`; `KNOWN_AGENTS` `profiles/policy.py:47`; `resolved_default_model_for_agent` `types.py:485`; `detect_available_agents` `_core/io.py:1448`; `cloud/preflight.py:39-43`.
2. **Resident is provider-neutral already** — `ManagedProviderCliAgentRunner` (`agent_loop.py:585-993`), stateless-per-turn LLM (Python composes full prompt, `runtime.py:988-1092`), session handshake `reserved_unconfirmed → persisted` (`provider_runtime.py:173-188`), `_normalize_*` evidence family (`:189-313`), provenance env (`provenance.py`).
3. **Sandbox reality** — hermes "sandbox" is in-process tool-layer path validation (ContextVar + monkeypatched handlers, pinned exec cwd; `arnold/agent/tools/sandbox.py`, `_sandbox_wrappers.py`, `workers/hermes.py:2571-2572`). **Not OS isolation.** omp `--yolo` = approval auto-accept; omp `bash` has no containment (`src/tools/bash.ts:1029`). Arnold sandbox cannot wrap an omp subprocess as-is.
4. **omp RPC** — JSONL stdio; events are `AgentSessionEvent` (usage/cost ride on **assistant messages**, `rpc-mode.ts:952-954`); **no enforced main-session structured output** (`outputSchema` is task/subagent-only); abort = in-process command, hard kill = SIGTERM→SIGKILL process group (`python/omp-rpc/client.py:234-278`; robomp precedent); sessions append-only JSONL; robomp respawns one process per task (`--session-dir` + `--continue`); model = `provider/modelId`; creds via env.
5. **Worker contract** — strict per-phase schemas `.megaplan/schemas/*.json` (gate all-required, `additionalProperties:false`), validated by `model_seam.capture_step_output`; retry per-transport; `fallback_chains.py` `classify_retryability` (18 classes, `:384`), `provider_family` `:308` → **`omp:deepseek:…` is family `'omp'` today** (needs upstream-family mapping); hermes persists per-step sessions in `state['sessions']`.
6. **Cloud/deploy** — surface = 6 wrappers + watchdog argv classifiers (`watchdog/processes.py:181-227`, cloud `arnold-watchdog:6168-6264`) + `arnold-heartbeat` (only tracks `codex exec -o /tmp/…`); `bakeoff/judge.py:130-134` spawns `run_agent.py`; **bun already in cloud image**; natives prebuilt linux-x64/arm64; **`agentbox-discord-resident.service:12` pins `MEGAPLAN_RESIDENT_MODEL_PROVIDER=hermes`**; **`entrypoint.sh.tmpl:9,68-70` creates/seeds `/root/.hermes`**.
7. **Consumer census** — ~45-60 executable Python consumers + 12 cloud/deploy consumers; `parallel_critique._run_check:293-365` deprecated/test-only; `cron/scheduler.py:268` bare-imports AIAgent (dead); `poms_skills/` live mirror of subagent-launcher; hermes-agent repo has **no live imports**.

## 2. SOL round-2 resolutions (each is an implementation gate, not aspiration)

1. **Spec grammar (fix):** exactly one form — `omp:<provider/modelId>` (e.g. `omp:deepseek/deepseek-v4-flash`). `parse_agent_spec` already yields agent=`omp`, model=`deepseek/deepseek-v4-flash`. Plan text corrected; no `omp:deepseek:…` double-colon form anywhere.
2. **Error mapping matrix (P0 deliverable):** explicit table — RPC launch failure / EOF / malformed JSONL / timeout / SIGTERM·SIGKILL / provider 429·5xx / auth / quota / unsupported model / context overflow / tool failure / missing final text / malformed payload / schema failure → classified as retryable-availability vs hard-error vs execute-blocked. **Generic adapter errors must NOT become availability failures.** Retries bounded and attempt-idempotent; execute-phase retries honor `ExecuteFallbackUnsafe` (`fallback_chains.py:445`).
3. **Direct/dispatcher parity (P0 test):** table-driven test that the `omp` branch (flag-OFF) and `OmpAdapter` (flag-ON) produce identical `WorkerResult` for the same fixtures.
4. **Resident-platform claim (fix §3):** a domain resident needs **four** things, not one file: (a) agent file (domain prompt + tool restriction), (b) tool/permission + credential/cwd policy, (c) session identity/persistence/resume/crash-recovery/concurrency, (d) evidence/output normalization into the resident store/manifest/ledger/notifications + supervision (watchdog/heartbeat/delivery). The Arnold resident already has (b)-(d); **Astrid must be built with all four or the platform claim is false.**
5. **Cloud closure (P1 additions):** migrate `agentbox-discord-resident.service` (`MEGAPLAN_RESIDENT_MODEL_PROVIDER=hermes` → `omp`; model env → `omp:…`) and `entrypoint.sh.tmpl` (drop `/root/.hermes` creation + hermes-auth seeding; keep codex seeding until codex adapter retires). Add a **categorized executable-reference acceptance test**: `rg -n "arnold\.agent|run_agent|launch_hermes|hermes_auth|\.hermes"` across source, systemd, cloud templates, docs/config examples, generated deployment artifacts, and test fixtures → zero production hits (historical docs allowed, classified).
6. **Delete-Hermes precondition (P2):** relocation is a **committed first step, not a parallel hope** — extract sandbox path validators + KeyPool into standalone `arnold_pipelines/megaplan/runtime/` modules (breaking the `arnold.agent.tools.*`/`providers.pool` imports), port the sandbox as an omp pre-exec wrapper, THEN delete. Acceptance = fresh-venv import + cold-start on a clean checkout, not `rg` alone.
7. **Fork-clean release gate (P0):** revert `src/task/agents.ts` + `src/prompts/agents/resident.md`; resident.md lives at `examples/agents/` + installed to `~/.omp/agent/agents/` by the launcher; launcher gets deterministic install/discovery (install-from-examples when missing; precedence project > user; hash/version pin); **cold-start test with empty caches** (a pre-unpacked `~/.omp/agent/agents/resident.md` on this machine must not mask fresh-machine failures); assert fork diff = `docs/agents.md` + `packages/coding-agent/scripts/agent` only.
8. **Watchdog correlation (P1):** argv `"omp"` is insufficient — the process shows as `bun …/src/cli.ts --mode rpc`. Correlate by process group + `--session-dir` path + plan/attempt token + cwd + birth time + heartbeat file. Killing the parent MUST kill the RPC child tree (process-group kill, already omp-rpc behavior). Tests: orphan, PID reuse, stale heartbeat, wrapper restart.
9. **Sandbox policy (P0, Linux agentbox):** bwrap — exact mount map, writable roots, credential exposure, `/tmp`, `.git`, symlink, child-process, and network policy must be **defined and tested on the actual agentbox**; cloud container ≠ per-run isolation (bubblewrap presence in the image ≠ working unprivileged user namespaces). macOS local: seatbelt. If bwrap proves non-functional on the box, fall back to (a) accept+document or (c) per-run container, decided at the P0 gate.
10. **Cost reconciliation (P0 adapter):** aggregate usage exactly once per RPC attempt; preserve input/output/cache-read/cache-write fields; attach model/provider identity; reconcile adapter totals vs ledger vs provider billing; **zero-cost or double-counted successful runs fail validation**.
11. **Session decision (P1):** v1 = **fresh stateless RPC session per turn** (no `--continue`; Python owns all context). omp-native continuation is deferred until replay tests pass (restart, retry, process kill, concurrent sessions, duplicate-prompt — asserting no duplicated hot context or stale state). This resolves the §3-vs-§4 duplication contradiction.
12. **Subagent fanout parity (P1 test):** RPC fanout (shared cwd, no worktrees) must prove output/timeout/cancellation/manifest parity vs today's hermes fanout.

## 3. Fork-cleanliness strategy (final)

| Facility | Home | Fork change |
|---|---|---|
| Agent definitions (resident, astrid-resident, …) | `~/.omp/agent/agents/*.md`, project `.omp/agents/*.md` | none |
| Agent examples (resident, template, astrid-resident) | fork `examples/agents/` | docs/examples only |
| `agent` launcher | `packages/coding-agent/scripts/agent` → `~/.bun/bin/agent` | 1 script (upstream `scripts/omp` pattern) |
| Platform docs | fork `docs/agents.md` | doc only |
| Domain tooling/hooks/notifications | omp extension (user-level or companion repo) | none |
| OmpAdapter / workers/omp.py / resident runner | Arnold repo | Arnold-side |

Release gate: fork diff = docs + 1 script; cold-start on empty caches; `src/` byte-identical to upstream HEAD.

## 4. Phases (unchanged in shape; gates per §2)

- **P0 — omp phase backend + bakeoff:** spec grammar, dispatch threading (branch table, `_is_agent_available`, KNOWN_AGENTS, `resolved_default_model_for_agent`, `detect_available_agents`, preflight hints, fallback family mapping), `workers/omp.py` adapter with error matrix + cost aggregation, sandbox policy decision (bwrap/seatbelt spec), fork-clean release gate, direct/dispatcher parity tests, **bakeoff omp-profile vs default-profile** (light → full; judge swapped to omp or kept-hermes-only until P2).
- **P1 — resident, subagents, cloud:** omp backend in `routing.py`/`agent_loop.py`/`provider_runtime.py` (fresh-stateless sessions, §2.11), RPC fanout parity, watchdog/heartbeat correlation, systemd/template migration, staging Discord op with store/manifest/ledger shape parity.
- **P2 — delete hermes:** relocation-first (§2.6), then delete, then acceptance (fresh-venv + cold-start + categorized rg audit), revert fork src changes already done in P0.
- **P3 — resident-agent platform:** ship `examples/agents/astrid-resident.md` with the full four-part resident contract (§2.4), optional Astrid extension, platform doc polish, live Astrid E2E.

## 5. What stays / dies

**Stays:** `contracts.py`, `dispatcher.py`, `costing/`, codex/claude CLI adapters, all orchestration, resident store/manifest/ledger writers, systemd/tmux supervision, relocated sandbox/key_pool, fork `docs/agents.md` + `scripts/agent`, user/project agent definitions, Astrid domain tooling as extension.
**Dies:** AIAgent runtime + tools, providers pool, SessionDB, cron, honcho, hermes_cli, `python -m arnold.agent.run_agent`, `workers/hermes.py`, hermes fanout, hermes subagent-launcher paths, DeepSeekAdapter, `_run_check`, `/root/.hermes` bootstrap, `MEGAPLAN_RESIDENT_MODEL_PROVIDER=hermes` default.

## 6. Confidence & release gates

SOL final: **72/100**. Showstopper named: a fresh deployment must run with **zero Hermes references** — close the live resident-service default + bootstrap paths first. To reach 90+ (SOL's own costed path):

1. **Hermes closure + fork-clean release gate** — exhaustive census, fresh-build/cache test, deployment/config cleanup, clean-diff assertion. (1-2d)
2. **OmpAdapter contract suite** — fake-RPC failure matrix, usage/cost reconciliation, direct/dispatcher parity, representative live phase corpus. (2-4d)
3. **Agentbox operational proof** — bwrap capability test, adversarial fs/process tests, watchdog/heartbeat recovery E2E, resident session replay. (2-3d)

Ladder: P0 gates → bakeoff parity → P1 staging parity → injected-failure suite → N green live runs → P2 deletion + acceptance → P3 Astrid live.

## Appendix — artifacts

- SOL r1 `/tmp/sol-review-1.md` · SOL r2 `/tmp/sol-review-2.md`
- Scouts (6): `HermesUsage`, `HermesContract`, `PhaseModelFlow`, `ResidentOps`, `PersistenceSurface`, `NonMegaplanTouch` (findings in v1 Appendix A/B)
- Scouts (7): `ConsumerCensus`, `PhaseDispatchMatrix`, `SandboxSecurity`, `WorkerContract`, `OmpRpcFacts`, `ResidentHotContext`, `CloudDeployment`
- v1 doc: `docs/omp-replaces-hermes-plan.md` history (git)
