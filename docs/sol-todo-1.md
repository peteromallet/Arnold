# Deliverable A — Executable to-do list

Execution rule: all tasks are strictly serial. No task is `PARALLEL-SAFE`; runtime fanout may retain its intended concurrency, but batches never overlap. Every Oracle Gate is mandatory. Failure loops to the first failed task in that batch, then reruns the gate; no downstream batch starts with an unresolved must-failure.

## B1 — Baseline, census, and provider contract (1 focused day)

1. Record `git rev-parse HEAD`, `git status --short`, `git diff --name-only`, and `git diff --check`. Preserve existing dirty work; classify every pre-existing path before editing.

   Done: execution evidence contains the baseline commit, dirty-path manifest, and no unowned path is overwritten.

2. Build the complete live-reference census across `arnold/`, `arnold_pipelines/`, `agentbox/`, `tests/`, `.github/`, deployment templates, `pyproject.toml`, `.env.example`, and generated-artifact inputs.

   Search for: `hermes:`, `arnold.agent`, `run_agent`, `launch_hermes`, `hermes_auth`, `.hermes`, `AIAgent`, `DeepSeekAdapter`, `workers.hermes`, and Hermes process argv.

   Done: every hit is classified as live, historical, or explicitly permitted transitional evidence.

3. Verify the omp registry and invocation contract in `/Users/peteromalley/Documents/oh-my-pi`: `packages/ai/src/registry/{deepseek,fireworks,zai,moonshot,openrouter,xai,anthropic}.ts`, `packages/ai/src/registry/oauth/kimi.ts`, `packages/coding-agent/src/cli/help-extra.ts`, `docs/models.md`, `python/omp-rpc/src/omp_rpc/{client,protocol}.py`, and `docs/rpc.md`.

   Produce the final Arnold→omp table: provider ID, model ID, effort/thinking flag, fallback family, credential environment variable, and no-spend validation command. Resolve the `kimi` versus `moonshot` choice and `--thinking` versus any legacy effort spelling.

   Done: no unresolved `⚠` row remains.

**Oracle Gate B1**

The oracle checks the dirty-path manifest, census completeness, and translation table.

Commands:

```bash
git diff --check
rg -n 'hermes:|arnold\.agent|run_agent|launch_hermes|hermes_auth|\.hermes|AIAgent|DeepSeekAdapter' arnold arnold_pipelines agentbox tests .github pyproject.toml .env.example
python -m pytest --collect-only -q
cd /Users/peteromalley/Documents/oh-my-pi && python3 -m pytest -q python/omp-rpc/tests
```

Any unclassified production hit, missing provider/credential row, or omp CLI/API mismatch returns to B1.

Dependency: every later adapter and migration task needs one canonical provider, credential, model, and effort contract.

## B2 — OmpAdapter, fake RPC server, errors, and cost (2–4 focused days)

1. Add `arnold_pipelines/megaplan/workers/omp.py` around the pinned `omp_rpc.RpcClient`; map Arnold `AgentRequest`/`AgentSpec` to provider/model, cwd, tools, max tokens, prompt, and effort/thinking.

   Use fresh stateless RPC sessions for v1. Python owns hot context; do not use continuation.

2. Implement the explicit error matrix in `workers/omp.py` and its tests:

   - launch failure, EOF, malformed JSONL, timeout;
   - SIGTERM/SIGKILL;
   - provider 429/5xx;
   - authentication, quota, unsupported model, context overflow;
   - tool failure, missing final text, malformed payload, schema failure.

   Map only availability/infrastructure failures to retryable fallback classes. Auth, quota, unsupported model, schema, malformed payload, tool, and side-effect failures must remain hard or execute-blocked. Enforce bounded attempts and `ExecuteFallbackUnsafe`.

3. Implement one centralized RPC-event→neutral-usage mapper. Aggregate assistant-message usage exactly once per RPC attempt, preserving input/output/cache-read/cache-write, provider/model identity, attempt ID, and cost metadata.

4. Add a deterministic fake RPC server and fixtures under `tests/workers/`, including valid output, tool loop, malformed frames, hangs, partial output, provider errors, and duplicate-event cases.

5. Route successful payloads through `model_seam.capture_step_output` and the existing strict schemas; reject prose contamination and unknown schema-owned fields.

   Done: `WorkerResult` has correct text, payload, failure class, usage, cost, provider/model, and attempt metadata for every fixture.

**Oracle Gate B2**

```bash
python -m pytest -q tests/workers/test_omp_adapter.py tests/arnold_pipelines/megaplan/test_model_seam_recovery.py tests/arnold_pipelines/megaplan/test_provider_contract_failure_routing.py
```

The oracle verifies every error row, retry count, no execute replay after side effects, no orphan child process, exact cost totals, and strict schema behavior. Any generic-error misclassification or cost discrepancy loops to B2.

Dependency: dispatch wiring must consume a proven adapter contract, not invent one while changing routing.

## B3 — Dispatch threading, availability, grammar, and fallback families (1.5–2 focused days)

1. Update `workers/_impl.py` functions `run_step_with_worker`, `_run_step_with_worker_legacy`, and the branch table so `omp` is a first-class direct-path worker and never reaches the empty-`resolved_model` assertion.

2. Update `_is_agent_available`, `profiles/policy.py:KNOWN_AGENTS`, `types.py:resolved_default_model_for_agent`, `_core/io.py:detect_available_agents`, and `cloud/preflight.py` availability hints.

3. Update `arnold/agent/contracts.py:parse_agent_spec`/`format_agent_spec` to enforce exactly `omp:<provider/modelId>` with optional Arnold-side effort suffix; preserve Claude/Codex compatibility.

4. Update `fallback_chains.py:provider_family` so `omp:deepseek/...`, `omp:zai/...`, etc. classify by upstream provider while retaining transport identity `omp`.

5. Add table-driven direct-path versus `MEGAPLAN_USE_AGENT_DISPATCHER=1` parity tests covering prep, plan, critique, revise, gate, finalize, execute, review, loop phases, tiebreakers, feedback, and critique evaluation.

   Done: identical fixture inputs produce identical `WorkerResult` objects and telemetry in both paths.

**Oracle Gate B3**

```bash
python -m pytest -q tests/arnold_pipelines/megaplan/test_omp_dispatch.py tests/arnold_pipelines/megaplan/test_fallback_chains.py tests/arnold_pipelines/megaplan/test_execute_flag_compat.py
```

The oracle checks every phase row, both dispatcher modes, availability detection, grammar rejection of double-colon omp specs, and cross-provider fallback rules.

Dependency: configuration migration must target a dispatch graph that is already complete.

## B4 — Model-reference and credential migration (1.5–2 focused days)

1. Translate all live profiles in `arnold_pipelines/megaplan/profiles/*.toml`, including `all-deepseek-*`, `all-fireworks-deepseek`, `all-open`, `apex`, and `arnold-openrouter`.

2. Update `profiles/policy.py` constants, `DEFAULT_AGENT_ROUTING`, `CANONICAL_PREP_MODELS`, `DIRECT_DEEPSEEK_V4_PRO_SPEC`, and the transitional model resolver in `arnold_pipelines/megaplan/runtime/key_pool.py`.

3. Migrate live references in `pipelines/live_supervisor/steps.py`, `audits/critique_evaluator.py`, `cloud/preflight.py`, `auto.py`, `orchestration/tiebreaker.py`, `megaplan/prompts/*`, `data/*_skill.md`, `data/_composed/*`, `AGENTS.md`, `.env.example`, and test/config fixtures.

4. Apply the final credential map, including `ZHIPU_API_KEY→ZAI_API_KEY`, Fireworks handling, native Kimi/Moonshot handling, OpenRouter, xAI, DeepSeek, Anthropic, and Codex.

   Done: all live specs use `omp:<provider/modelId>`; translation is semantic, not textual rename; historical `.megaplan/**` hits are classified.

**Oracle Gate B4**

```bash
python -m pytest -q tests/arnold_pipelines/megaplan/test_profile_policy.py tests/arnold_pipelines/megaplan/test_routing_source_invariants.py tests/arnold_pipelines/megaplan/test_model_reference_migration.py
rg -n 'omp:[^/]+:' arnold arnold_pipelines tests
```

The oracle checks no double-colon omp specs, profile loading, env hints, credential names, and only the explicitly assigned cloud/service residuals. Unexpected Hermes hits loop to B4.

Dependency: the bakeoff and resident work must run against the canonical model and credential surface.

## B5 — Sandbox policy and fork-clean omp release (2–3 focused days)

1. Define the Linux bwrap policy in the omp pre-exec wrapper: read-only source mounts, writable plan/worktree roots, credential exposure, `/tmp`, `.git`, symlink behavior, child processes, network, and process-group ownership.

2. Test it on the actual agentbox, not merely the Docker image. Test absolute-path writes, `cd`, symlink escapes, `/tmp`, `.git`, child-process persistence, and network access. Define macOS seatbelt behavior separately. Reject unsandboxed `--yolo` for execute.

3. In oh-my-pi, revert `packages/coding-agent/src/task/agents.ts` and `packages/coding-agent/src/prompts/agents/resident.md`. Move resident/template/Astrid examples to `examples/agents/`.

4. Finalize `packages/coding-agent/scripts/agent` and `docs/agents.md`: deterministic project-over-user precedence, bundled installation, cache invalidation, hash/version pinning, and empty-cache behavior.

5. Build omp from an empty `HOME`, empty `~/.omp`, and empty package/build caches.

   Done: adversarial sandbox tests pass; `src/` is byte-identical to upstream; only `docs/agents.md`, `examples/agents/*`, and the single launcher script are permitted fork changes.

**Oracle Gate B5**

```bash
bwrap --version
python -m pytest -q tests/sandbox/test_omp_sandbox.py
cd /Users/peteromalley/Documents/oh-my-pi && bun run check:ts
git diff --name-only <upstream-omp-head>
```

The oracle inspects actual agentbox evidence and the clean fork diff. Any escape, cache-masked discovery, or unexpected omp `src/` change loops to B5.

Dependency: no phase bakeoff is meaningful until tool safety and fork provenance are proven.

## B6 — P0 parity corpus and bakeoff (1–2 focused days)

1. Create the omp profile from the B4 translation table and commit only in-scope migration files after auditing the dirty-path manifest.

2. Run the existing bakeoff machinery (`arnold_pipelines/megaplan/bakeoff/*`) comparing the omp profile with the B1 recorded default profile, at light and full robustness.

3. Score plan, critique, gate, revise, finalize, execute, schema validity, artifact writes, cost, latency, retry behavior, and wrong-tree writes. Use an omp judge where supported; use the pre-migration judge only as a recorded baseline, never as a new live dependency.

**Oracle Gate B6**

```bash
python -m arnold_pipelines.megaplan bakeoff run --idea-file <fixture> --profiles <omp-profile> <baseline-profile> --robustness light
python -m arnold_pipelines.megaplan bakeoff run --idea-file <fixture> --profiles <omp-profile> <baseline-profile> --robustness full
python -m pytest -q tests/bakeoff tests/arnold_pipelines/megaplan/test_omp_dispatch.py
```

The oracle requires persisted comparison evidence with no must-level regression. Failure loops to the responsible P0 batch.

Dependency: P1 resident and cloud changes start only after phase-worker parity.

## B7 — Resident omp backend and stateless session semantics (2–3 focused days)

1. Update `arnold/agent/routing.py`: `MANAGED_AGENT_BACKENDS`, `DEFAULT_MANAGED_AGENT_MODELS`, `MANAGED_AGENT_CAPABILITIES`, `infer_managed_agent_backend`, and `resolve_managed_agent_route`.

2. Update `resident/agent_loop.py:ManagedProviderCliAgentRunner` and `_command` for omp RPC, tool policy, cwd, credentials, timeout, process group, and fresh stateless sessions.

3. Add omp normalization to `resident/provider_runtime.py`: replace the Hermes evidence path with `_normalize_omp`, session identity, assistant text, tool events, usage, failure categories, and normalized event files.

4. Update `resident/config.py` defaults and `resident/runtime.py` model-seam metadata. Python must compose full context; omp must not receive duplicated persisted hot context.

5. Extend `tests/resident/test_managed_provider_agent_runner.py`, `test_provider_runtime.py`, and add deterministic restart/retry/concurrent-session/duplicate-prompt replay tests.

**Oracle Gate B7**

```bash
python -m pytest -q tests/resident/test_managed_provider_agent_runner.py tests/resident/test_provider_runtime.py tests/resident/test_context_tree.py tests/resident/test_turn_handoff.py
```

The oracle compares resident store, manifest, ledger, evidence, notification, and session-handshake shapes against existing provider fixtures. Any duplicated context or missing final response loops to B7.

Dependency: subagent fanout and staging must use the same resident backend contract.

## B8 — RPC subagent fanout parity (1.5–2 focused days)

1. Replace Hermes fanout in `resident/subagent.py`, `resident/subagent_worker.py`, `agent_runtime/process_fanout.py`, and `_core/worker_fanout.py` with one separate `RpcClient` per unit, shared cwd, no worktrees.

2. Replace `orchestration/parallel_critique.py:_run_check` and any `AIAgent`-constructed test/deprecated path with the RPC fanout contract.

3. Preserve output, timeout, cancellation, restart, manifest, ledger, and delivery semantics. Do not use omp `task` unless a separate isolation decision is recorded.

**Oracle Gate B8**

```bash
python -m pytest -q tests/characterization/test_agent_fanout_boundaries.py tests/resident/test_launch_subagent.py tests/resident/test_subagent_restart_persistence.py tests/arnold_pipelines/megaplan/test_worker_fanout_fallback.py
```

The oracle requires parity fixtures for success, timeout, cancellation, partial output, and child cleanup. Any worktree creation or manifest drift loops to B8.

Dependency: cloud repair and watchdog paths must supervise the final RPC process shape.

## B9 — Cloud wrappers, watchdog, heartbeat, systemd, and templates (2–3 focused days)

1. Migrate every Hermes-bearing wrapper, not only the original six: `arnold-repair-loop`, `arnold-watchdog`, `arnold-meta-repair-loop`, `arnold-progress-auditor`, `arnold-resident-schedule-run-once-r7`, `arnold-kimi-goal-operator`, `arnold-run`, `arnold-supervise`, `bakeoff/judge.py`, and sibling wrappers.

2. Replace watchdog functions `kimi_operator_running`, `reap_stale_repair_candidates`, `classify_kind`, and `extract_session` so omp is correlated by process group, `--session-dir`, plan/attempt token, cwd, birth time, and heartbeat—not by literal argv `"omp"`.

3. Update `arnold-heartbeat` and `mp-heartbeat` to observe omp RPC activity and kill the whole process group on stale heartbeat.

4. Update `agentbox/systemd/agentbox-discord-resident.service`, all cloud systemd units, `cloud/templates/entrypoint.sh.tmpl`, `Dockerfile`, and bootstrap scripts. Remove `/root/.hermes` creation/auth seeding; install and smoke-test pinned Bun/omp/omp-rpc.

**Oracle Gate B9**

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/*
bash -n arnold_pipelines/megaplan/cloud/systemd/*
python -m pytest -q tests/cloud/test_watchdog_wrappers.py tests/arnold_pipelines/megaplan/watchdog/test_liveness_correlation_authority.py tests/cloud/test_cloud_dockerfile_tool_versions.py
rg -n 'hermes:|run_agent|launch_hermes|hermes_auth|\.hermes' arnold_pipelines/megaplan/cloud agentbox
```

The oracle runs orphan, PID-reuse, stale-heartbeat, and wrapper-restart fixtures and checks generated deployment output. Any blind spot or Hermes bootstrap path loops to B9.

Dependency: staging must exercise the same deployment and custody paths that production will use.

## B10 — Agentbox staging, replay, fault injection, and green runs (2–3 focused days)

1. Deploy the migrated resident to the actual agentbox/Hetzner path and run normal Discord turn, tool turn, restart, concurrent messages, cancellation, timeout, and recovery.

2. Replay RPC transcripts across process restart, retry, process kill, concurrent sessions, and duplicate prompt. Assert no duplicated hot context, stale state, duplicate execute, or duplicate delivery.

3. Run injected launch/EOF/malformed-frame/timeout/429/5xx/auth/schema failures through resident and watchdog recovery.

4. Complete three consecutive green live phase runs plus one green resident Discord run, with ledger, manifest, evidence, and process-tree artifacts retained.

**Oracle Gate B10**

The oracle inspects journal/manifests/ledger and runs:

```bash
python -m pytest -q tests/resident tests/cloud tests/arnold_pipelines/megaplan/watchdog tests/fixer_replay
journalctl -u agentbox-discord-resident.service --since <run-start>
ps -eo pid,ppid,pgid,args
```

Any orphan, replay divergence, cost mismatch, wrong-tree write, or duplicate side effect loops to B7–B10 as appropriate.

Dependency: deletion is safe only after the replacement is operationally proven.

## B11 — Relocation-first Hermes deletion (2–3 focused days)

1. Extract sandbox validators and wrappers from `arnold.agent.tools.sandbox` and `_sandbox_wrappers` into standalone `arnold_pipelines/megaplan/runtime/sandbox.py`; no new module may import the old package.

2. Extract KeyPool and credential helpers from `arnold.agent.providers.pool` into `arnold_pipelines/megaplan/runtime/key_pool.py`, retaining governor/envelope charging but removing Hermes env/home semantics.

3. Port all consumers: resident runtime, preflight, profiles, workers, tests, and cloud code. Keep only neutral contracts, dispatcher, costing, and relocated runtime modules.

4. Delete `workers/hermes.py`, Hermes fanout/launcher paths, `DeepSeekAdapter`, `AIAgent` runtime/tools, providers pool, SessionDB, cron/honcho/Hermes CLI paths, and tests asserting implementation internals. Remove Hermes dependencies/comments from `pyproject.toml`.

5. Validate a fresh environment before final cleanup.

**Oracle Gate B11**

```bash
rg -n 'from arnold\.agent\.tools|arnold\.agent\.providers\.pool|AIAgent|DeepSeekAdapter|workers\.hermes|launch_hermes|run_agent' arnold arnold_pipelines agentbox tests pyproject.toml
python -m compileall -q arnold arnold_pipelines agentbox
python -P -c "import arnold; import arnold_pipelines.megaplan; import arnold_pipelines.megaplan.runtime.sandbox; import arnold_pipelines.megaplan.runtime.key_pool"
python -m pytest --collect-only -q
```

Any import-back edge or cold-start failure loops to relocation, consumer migration, then deletion.

Dependency: final acceptance cannot be meaningful while deleted modules remain importable.

## B12 — Resident-agent platform, Astrid, and generator (2–3 focused days)

1. Add a streamlined resident generator under `arnold_pipelines/megaplan/resident/` and expose it through `resident/cli.py`. It must scaffold all four contracts: agent prompt, tool/permission/credential/cwd policy, session identity/persistence/recovery/concurrency, and evidence/output normalization plus supervision/delivery.

2. Add `examples/agents/astrid-resident.md` and the corresponding Arnold-side domain extension/configuration. Do not modify omp `src/`.

3. Wire Astrid tools, credentials, cwd policy, resident store/manifest/ledger output, notifications, heartbeat, watchdog classification, restart recovery, and one live end-to-end run.

4. Document the reusable platform contract in `docs/agents.md` and test deterministic generation plus project-over-user installation.

**Oracle Gate B12**

```bash
python -m pytest -q tests/resident/test_resident_generator.py tests/resident/test_astrid_resident.py
python -m arnold_pipelines.megaplan resident --help
```

The oracle inspects generated files and live Astrid evidence, not only the final assistant message. Missing any of the four contracts loops to B12.

Dependency: Astrid must be built on the proven resident platform, not used to discover basic platform semantics.

## B13 — Final release gate (1–2 focused days)

1. Run the categorized acceptance scan over live source, config, deployment, generated artifacts, and fixtures:

   ```bash
   rg -n 'hermes:|arnold\.agent|run_agent|launch_hermes|hermes_auth|\.hermes' arnold arnold_pipelines agentbox tests .github scripts pyproject.toml .env.example
   ```

2. Confirm all remaining hits are only in the explicit historical allowlist: `.megaplan/**`, archived documents, and the design/review artifacts.

3. Re-run full focused tests, fresh import/cold-start, fork diff, bakeoff evidence, resident replay, watchdog fault matrix, and three-green-run evidence.

4. Produce the release manifest containing commit hash, fork hash, translation-table hash, test commands/results, sandbox evidence, bakeoff comparison, replay corpus, and historical-hit allowlist.

**Final Oracle Gate**

No live Hermes reference, no old import, no stale deployment default, no fork `src/` delta, no cost mismatch, no orphan process, and no failed must criterion. Failure routes back to the originating batch; the final gate never accepts a patch-only explanation.

# Deliverable B — Unknowns to explore now

These are read-only, dispatch-ready probes, ranked by confidence gain per effort.

## U1 — What is the exact cold-start omp provider/model/credential contract?

- **Question:** Are `deepseek`, `fireworks`, `zai`, `openrouter`, `xai`, `anthropic`, and the intended Kimi route all accepted with the final `provider/modelId` strings, and does effort map to `--thinking`/`RpcClient(thinking=...)`?
- **Look:** omp `packages/ai/src/registry/*.ts`, `packages/ai/src/registry/oauth/kimi.ts`, `packages/coding-agent/src/cli/flag-tables.ts`, `python/omp-rpc/src/omp_rpc/client.py`, Arnold `runtime/key_pool.py`.
- **Confidence up/down:** Every selector resolves in a cold model registry with the expected env key; down if Kimi, Fireworks, or ZAI requires a different provider/model or credential path.
- **Cheapest probe:** Static read plus no-spend RPC `get_state`/`set_model`.

## U2 — Can the deployment ship and invoke the pinned omp build reproducibly?

- **Look:** oh-my-pi `package.json`, `packages/coding-agent/package.json`, `python/omp-rpc/pyproject.toml`, Arnold `cloud/templates/Dockerfile`, `entrypoint.sh.tmpl`, all wrapper launchers.
- **Up/down:** A fresh container has Bun, the omp binary, and importable `omp_rpc`; down if PATH, editable-install, native binary, or permissions differ.
- **Cheapest probe:** Static dependency census followed by one empty-cache container/bootstrap smoke.

## U3 — What is the reliable structured-output path for main RPC phases?

- **Look:** Arnold `model_seam.py`, `schemas/*.json`, omp `docs/rpc.md`, `modes/rpc/rpc-types.ts`, `modes/rpc/rpc-mode.ts`, `task/structured-subagent.ts`.
- **Up/down:** Repeated plan/critique/gate/execute outputs pass `capture_step_output`; down if final text contains tool traces, truncates, or cannot carry strict schemas.
- **Cheapest probe:** Fake RPC fixtures plus one small live prompt per representative phase.

## U4 — Does the chosen bwrap policy actually work on the agentbox?

- **Look:** Arnold `runtime/sandbox.py`, cloud `Dockerfile`, omp `packages/coding-agent/src/tools/bash.ts`, `python/omp-rpc/src/omp_rpc/client.py`.
- **Up/down:** Adversarial path, symlink, `/tmp`, `.git`, child-process, and network tests stay within policy; down on any escape or unavailable unprivileged namespace.
- **Cheapest probe:** One disposable agentbox canary.

## U5 — Which omp usage source is authoritative for cost reconciliation?

- **Look:** omp `python/omp-rpc/src/omp_rpc/protocol.py` (`AssistantMessage`, `Usage`, `SessionStats`), `modes/rpc/rpc-mode.ts`, `session/session-stats.ts`; Arnold costing and ledger writers.
- **Up/down:** Per-attempt assistant usage sums exactly to `get_session_stats` and Arnold ledger; down on multi-assistant/tool-loop double counting or zero-cost success.
- **Cheapest probe:** Capture one transcript and compare event aggregation with `get_session_stats`.

## U6 — Does the current checkout contain dispatch bypasses beyond the plan census?

- **Look:** `workers/_impl.py`, `arnold/agent/`, `_core/*fanout.py`, `orchestration/parallel_critique.py`, `cron/scheduler.py`, cloud judge/repair paths.
- **Up/down:** Every phase and helper has a direct and dispatcher route; down on any `AIAgent` construction, subprocess launcher, or hidden allowlist.
- **Cheapest probe:** Static import/process scan plus `pytest --collect-only`.

## U7 — Can sandbox and KeyPool relocation break the neutral import graph?

- **Look:** `runtime/{sandbox,key_pool}.py`, `arnold/agent/tools/{sandbox,_sandbox_wrappers}.py`, `arnold/agent/providers/pool.py`, `resident/runtime.py`, package metadata.
- **Up/down:** New modules import without `arnold.agent` runtime; down if neutral contracts transitively import the deleted agent tree.
- **Cheapest probe:** Static import graph and fresh-venv import test.

## U8 — Will the watchdog recognize real omp RPC processes without false positives?

- **Look:** `cloud/wrappers/arnold-watchdog`, `watchdog/{correlate,processes,orphans}.py`, heartbeat wrappers, omp RPC process-group code.
- **Up/down:** Synthetic `bun … src/cli.ts --mode rpc` tables correctly handle orphan, PID reuse, stale heartbeat, and restart; down on argv-only classification.
- **Cheapest probe:** Fake process-table fixtures; no live model call needed.

## U9 — Does the resident stateless runner preserve Arnold’s context and evidence semantics?

- **Look:** `resident/{agent_loop,provider_runtime,runtime,context_tree}.py`, resident tests, `omp_rpc` `no_session` behavior.
- **Up/down:** Restart/retry/concurrent-session replay has one intended context and identical manifest/ledger shape; down on stale session IDs or duplicated prompt history.
- **Cheapest probe:** Deterministic fake provider, then one staging turn.

## U10 — Does RPC fanout preserve shared-cwd/no-worktree behavior?

- **Look:** `resident/{subagent,subagent_worker}.py`, `agent_runtime/process_fanout.py`, `_core/worker_fanout.py`, `orchestration/parallel_critique.py`, omp `modes/rpc/rpc-subagents.ts`.
- **Up/down:** Output, timeout, cancellation, process cleanup, manifest, and delivery match current fixtures; down on implicit task worktrees or lost cancellation.
- **Cheapest probe:** Fake RPC server with two concurrent units.

## U11 — Is the fork-clean release reproducible from empty caches?

- **Look:** oh-my-pi dirty diff, `packages/coding-agent/src/task/agents.ts`, `src/task/discovery.ts`, `src/prompts/agents/resident.md`, `scripts/agent`, `examples/agents`, build/dist outputs.
- **Up/down:** Fresh build and empty `HOME` discover project/user/bundled agents with only approved docs/examples/script changes; down if cached bundled agents mask failure or generated source changes.
- **Cheapest probe:** Static diff plus isolated `HOME`/`PI_CODING_AGENT_DIR` smoke.

## U12 — Is the cloud census complete beyond the named wrappers?

- **Look:** every file under `cloud/wrappers/`, `cloud/systemd/`, `cloud/templates/`, `agentbox/systemd/`, plus generated deployment artifacts. Current checkout already exposes extra paths such as `arnold-resident-schedule-run-once-r7`, `arnold-meta-repair-loop`, and `arnold-progress-auditor`.
- **Up/down:** No live launcher, auth seed, service default, or skill path contains Hermes; down on any unclassified production hit.
- **Cheapest probe:** Static scan of shell/Python strings and generated templates.

## U13 — What is the actual Astrid domain surface to integrate?

- **Question:** Where are Astrid’s CLI gateway, credentials, tool restrictions, output artifacts, and delivery expectations defined?
- **Look:** Arnold `.megaplan/initiatives/astrid-consumer/{NORTHSTAR.md,README.md,briefs/*}`, `resident/tool_registry.py`, `resident/delivery_effects.py`, `resident/managed_child_custody.py`, and the Astrid skill/repository if separately available.
- **Up/down:** A stable domain API and testable artifact contract raises confidence; absence of an actual Astrid tool surface blocks a truthful P3 implementation.
- **Cheapest probe:** Static locate/read first, then one dry-run with fake Astrid tools.

Dispatch note: the prescribed Megaplan launcher was probed but is unavailable in this read-only checkout, so these are prepared as exploration briefs rather than claimed subagent results.
