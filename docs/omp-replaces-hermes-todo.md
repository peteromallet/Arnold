> **Authority status (T44):** Zero-authority historical planning artifact — for reference only; not live operational authority. Canonical delegation is via the megaplan CLI and the migrated wrappers.

# omp replaces Hermes — Executable To-Do List (execution contract)

**Status:** FINAL. Sol (gpt-5.6, max reasoning) solidified pass: HOLISTIC / COMPLETE, 94/100, zero remaining unknowns.
**Provenance:** plan v3.1 (docs/omp-replaces-hermes-plan.md) -> sol pass 1 (/tmp/sol-todo-1.md) -> 13 unknown scouts (U1-U13, results /tmp/unknowns-results.md) -> sol solidify pass (below). 2026-08-10.

---

# FINAL — SOLIDIFIED executable to-do list

Goal: replace every live Hermes path in Arnold with omp, make omp the resident-agent platform with Astrid as the concrete example, and keep the omp fork clean with zero live Hermes traces.

Execution is strictly serial: complete B1, pass its oracle gate, then start B2. Runtime fanout may remain concurrent where explicitly required, but batches never overlap. Every gate is mandatory. A failed gate loops to the first failed task in that batch; no downstream batch starts with an unresolved must-failure.

## Prerequisites & environment (before B1)

- **Workspace**: Arnold checkout at /Users/peteromalley/Documents/Arnold (dirty tree is handled by B1's baseline manifest; do not stash). omp checkout at /Users/peteromalley/Documents/oh-my-pi (editable; upstream `origin` present for B5's fork-diff gate). Codex CLI installed (gpt-5.6-luna configured). bun >= 1.3.14.
- **Credentials** (names only; who provides them): DEEPSEEK_API_KEY (confirmed present), plus keys for every provider actually used by the migrated profiles — FIREWORKS_API_KEY, ZAI_API_KEY, OPENROUTER_API_KEY, XAI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, MOONSHOT/KIMI — provision as each profile is migrated (B4); omp reads them from env.
- **Agentbox/Hetzner access** for B5 (trusted-container decision), B9 (deploy), B10 (staging): ssh + ability to install/restart services; Discord bot token + staging channel for B10 resident turns.
- **Astrid repo** on disk (exists: ~/Documents/reigh-workspace/Astrid) for B12.
- **Out-of-tree residues to clean alongside B11/B13** (outside the repo, not covered by the release-gate scan): `~/.claude/skills/subagent-launcher/*` (user-level hermes launcher copy used by the subagent-launcher skill), `~/.claude/skills/` hermes references in skill docs, `~/Documents/poms_skills/subagent-launcher/` mirror, `~/Documents/hermes-agent` skill docs (historical-only, classified).
- **Out of scope of this contract (separate follow-ons, not blockers)**: the branded-CLI rebrand (Level-2 `APP_NAME` patch set), the omp fork GitHub remote + release tag (needed only when distributing; local checkout suffices for B1-B13), sprint briefs in `.megaplan/briefs/` format (cut from batches on demand).

Coverage note: B1-B13 cover every live surface known to the census (which itself caught 5 extra cloud surfaces in exploration). "Absolutely everything" is enforced by the mechanism, not assumed: each oracle gate checks its batch's evidence, and B13's categorized acceptance scan (`rg hermes:|arnold.agent|run_agent|launch_hermes|hermes_auth|\.hermes` over live dirs → zero) is the final net — any surface the census missed surfaces there and loops to its batch.

## B1 — Baseline, census, and final provider contract

1. Record `git rev-parse HEAD`, `git status --short`, `git diff --name-only`, and `git diff --check`. Preserve and classify all existing dirty paths.

2. Census every live reference across Arnold source, tests, deployment, templates, generated-artifact inputs, `pyproject.toml`, `.env.example`, and `.github`.

   Search for:

   `hermes:`, `arnold.agent`, `run_agent`, `launch_hermes`, `hermes_auth`, `.hermes`, `AIAgent`, `DeepSeekAdapter`, `workers.hermes`, Hermes argv, `_compatibility.py` handling of `--hermes`/`--phase-model`, and `cloud/summarize_fixer_session.py` launcher assumptions.

   Classify every hit as live, historical, or explicitly permitted transitional evidence. U6 found no additional bypasses beyond this census.

3. Freeze the final omp contract from the catalog, registry, RPC client, and environment-variable documentation. The only Arnold omp grammar is:

   `omp:<provider/modelId>`

   An optional Arnold-side effort suffix is stored separately and becomes omp `--thinking <level>` / `RpcClient(thinking=...)`. Never emit `omp:provider:model`.

   | Route | Canonical catalog model | Credential |
   |---|---|---|
   | DeepSeek | `deepseek/deepseek-v4-pro` or `deepseek/deepseek-v4-flash` | `DEEPSEEK_API_KEY` |
   | Fireworks | `fireworks/kimi-k2.7-code` | `FIREWORKS_API_KEY` |
   | zAI | `zai/glm-5.2` | `ZAI_API_KEY` |
   | Moonshot | `moonshot/kimi-k2.7-code` | `MOONSHOT_API_KEY` or `KIMI_API_KEY` |
   | Kimi Code OAuth | `kimi-code/kimi-for-coding` | Kimi OAuth / `KIMI_API_KEY` |
   | OpenRouter | exact catalog IDs such as `openrouter/openai/gpt-5.5` and the selected OpenRouter DeepSeek catalog row | `OPENROUTER_API_KEY` |
   | xAI | `xai/grok-4-fast-non-reasoning` | `XAI_API_KEY` |
   | Anthropic | `anthropic/claude-opus-4-8` | `ANTHROPIC_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` |

   Valid thinking levels are `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, and CLI-level `auto`; the RPC client receives only its supported typed levels. Catalog per-host maps are authoritative: OpenRouter is high-only; Kimi K3 supports its low/high/max map; GLM-5.2 uses high/max; Fireworks maps `minimal` to provider `none`, with the remaining host-specific mappings copied exactly from `model-thinking.ts`.

   Freeze provider family as the upstream provider while retaining transport identity `omp`. Attach a no-spend validation command for every row using registry/model lookup and RPC `get_state`/`set_model`; no live completion is required.

**Oracle Gate B1**

```bash
git diff --check
rg -n 'hermes:|arnold\.agent|run_agent|launch_hermes|hermes_auth|\.hermes|AIAgent|DeepSeekAdapter' arnold arnold_pipelines agentbox tests .github pyproject.toml .env.example
python -m pytest --collect-only -q
cd /Users/peteromalley/Documents/oh-my-pi && python3 -m pytest -q python/omp-rpc/tests
```

The oracle checks the dirty-path manifest, complete census, all eight final provider rows, exact catalog IDs, credentials, thinking maps, and no unresolved verification caveat.

## B2 — OmpAdapter, structured output, errors, and cost

1. Add `arnold_pipelines/megaplan/workers/omp.py` around the pinned `omp_rpc.RpcClient`. Map `AgentRequest`/`AgentSpec` to provider, exact catalog model, cwd, tools, max tokens, prompt, and thinking level. Use a fresh stateless RPC session per attempt; Python owns hot context and omp continuation is not used.

2. Implement strict structured output using the codex local-strict mechanism:

   - allocate `capture_recovery.output_path`;
   - include `response_enforcement_attestation`;
   - give the model a tool that writes the phase payload to that path;
   - read and validate the file through `model_seam.capture_step_output`;
   - use exact JSON parsing and schema validation;
   - use `_extract_json_candidates_from_raw` only as a fallback for recovery;
   - reject prose contamination, markdown-only payloads, truncation, and unknown schema-owned fields.

3. Implement and test the complete error matrix:

   - launch failure, EOF, malformed JSONL, timeout;
   - SIGTERM/SIGKILL;
   - provider 429/5xx;
   - authentication, quota, unsupported model, context overflow;
   - tool failure, missing final text, malformed payload, schema failure.

   Only availability/infrastructure failures are retryable fallback classes. Authentication, quota, unsupported model, context overflow, tool, malformed payload, schema, and side-effect failures remain hard or execute-blocked. Retries are bounded, attempt-idempotent, and obey `ExecuteFallbackUnsafe`.

4. Centralize RPC-event-to-neutral-usage mapping. The authoritative source is `usage` on each `AssistantMessage`. Aggregate each assistant message exactly once per RPC attempt, preserving input, output, cache-read, cache-write, provider, model, attempt ID, and cost metadata. Reconcile against derived `get_session_stats`; mirror the codex delta-from-cumulative exactly-once pattern before emitting Arnold ledger receipts.

5. Add deterministic fake RPC fixtures for valid output, tool loops, structured-file output, malformed frames, hangs, partial output, provider failures, duplicate assistant events, retry, cancellation, and cost reconciliation.

**Oracle Gate B2**

```bash
python -m pytest -q \
  tests/workers/test_omp_adapter.py \
  tests/arnold_pipelines/megaplan/test_model_seam_recovery.py \
  tests/arnold_pipelines/megaplan/test_provider_contract_failure_routing.py
```

The oracle verifies the full error matrix, strict structured output, bounded retries, no execute replay after side effects, no orphan child, exact per-attempt cost, and reconciliation with derived session statistics.

## B3 — Dispatch threading, availability, grammar, and fallback families

1. Update `workers/_impl.py` (`run_step_with_worker`, `_run_step_with_worker_legacy`, and the branch table) so omp is a first-class direct worker and never reaches the empty-`resolved_model` assertion.

2. Update `_is_agent_available`, `profiles/policy.py:KNOWN_AGENTS`, `types.py:resolved_default_model_for_agent`, `_core/io.py:detect_available_agents`, and `cloud/preflight.py`.

3. Make `parse_agent_spec`/`format_agent_spec` enforce exactly `omp:<provider/modelId>` with an optional Arnold-side effort suffix while preserving Claude/Codex compatibility.

4. Make `fallback_chains.provider_family` classify `omp:deepseek/...`, `omp:zai/...`, and all other omp routes by upstream provider.

5. Add table-driven parity tests for direct execution and `MEGAPLAN_USE_AGENT_DISPATCHER=1` across prep, plan, critique, revise, gate, finalize, execute, review, loop phases, tiebreakers, feedback, and critique evaluation.

**Oracle Gate B3**

```bash
python -m pytest -q \
  tests/arnold_pipelines/megaplan/test_omp_dispatch.py \
  tests/arnold_pipelines/megaplan/test_fallback_chains.py \
  tests/arnold_pipelines/megaplan/test_execute_flag_compat.py
```

The oracle checks every phase, both dispatch modes, availability detection, rejection of double-colon omp specs, and cross-provider fallback behavior.

## B4 — Model-reference and credential migration

1. Translate every live profile in `arnold_pipelines/megaplan/profiles/*.toml`, including all DeepSeek, Fireworks, Open, Apex, and OpenRouter profiles.

2. Update `profiles/policy.py`, `DEFAULT_AGENT_ROUTING`, `CANONICAL_PREP_MODELS`, `DIRECT_DEEPSEEK_V4_PRO_SPEC`, and the transitional resolver in `runtime/key_pool.py` to consume the final B1 table.

3. Migrate live references in supervisor steps, critique evaluation, preflight, `auto.py`, tiebreakers, prompts, skills, composed data, `AGENTS.md`, `.env.example`, and test/config fixtures.

4. Apply the final credential map, including `ZHIPU_API_KEY → ZAI_API_KEY`, Fireworks, native Moonshot/Kimi Code, OpenRouter, xAI, DeepSeek, Anthropic, and retained Codex/Claude routes.

5. Pass thinking/effort through `--thinking <level>` using the frozen per-host catalog maps. Do not silently normalize all hosts to one universal effort ladder.

**Oracle Gate B4**

```bash
python -m pytest -q \
  tests/arnold_pipelines/megaplan/test_profile_policy.py \
  tests/arnold_pipelines/megaplan/test_routing_source_invariants.py \
  tests/arnold_pipelines/megaplan/test_model_reference_migration.py
rg -n 'omp:[^/]+:' arnold arnold_pipelines tests
```

The oracle requires all live specs to use exact `omp:<provider/modelId>` form, valid profile loading, correct credentials, correct effort mapping, and no unexpected live Hermes references.

## B5 — Agentbox security decision and fork-clean omp release

1. Record the final security decision: bwrap is not viable on the agentbox because unprivileged user namespaces are deliberately disabled. Do not require bwrap-on-box execution.

2. Accept and document the actual boundary:

   - container isolation plus explicit `MEGAPLAN_TRUSTED_CONTAINER=1`;
   - relocated in-process path validators for plan/worktree writes and command cwd;
   - `--yolo` is approval auto-accept, not filesystem containment;
   - process-group ownership and group kill remain mandatory;
   - inherited network is documented;
   - writable roots are plan directory, `~/.omp`, `/tmp`, `/var/tmp`, `/dev/shm`, and required Git identity files.

   Retain the managed-agent mount map and adversarial mount/test matrix as a contingency specification for a future per-run isolation environment, not as an agentbox acceptance requirement.

3. In oh-my-pi, perform exactly the known fork cleanup: delete the untracked resident prompt and revert the two-line `src/task/agents.ts` resident import/embedded-definition change. Keep resident/template/Astrid examples under `examples/agents/`.

4. Finalize `packages/coding-agent/scripts/agent` and `docs/agents.md` with project-over-user precedence, bundled installation, deterministic discovery, cache invalidation, hash/version pinning, and empty-cache behavior.

5. Smoke from an empty `HOME`, empty `~/.omp`, empty `~/.omp/agent/agents`, empty `~/.omp/agent/.prompts`, empty project `.omp/agents`, and empty package/build caches. Account for the in-memory bundled-agent cache being per-process; every cold-start assertion must use a fresh process.

**Oracle Gate B5**

```bash
python -m pytest -q tests/sandbox/test_omp_sandbox.py
cd /Users/peteromalley/Documents/oh-my-pi && bun run check:ts
git diff --name-only <upstream-omp-head>
```

The oracle checks actual container/trusted-mode evidence, relocated validator behavior, path/symlink/command tests, empty-cache discovery, exact fork cleanup, byte-identical omp `src/`, and an allowed diff limited to docs, examples, and the launcher. There is no bwrap-on-box check.

## B6 — P0 parity corpus and bakeoff

1. Create the omp profile from the B1/B4 table and modify only audited in-scope paths.

2. Run the existing bakeoff machinery against the recorded pre-migration baseline at light and full robustness.

3. Score plan, critique, gate, revise, finalize, execute, schema validity, artifact writes, cost, latency, retry behavior, wrong-tree writes, and judge behavior. Use an omp judge where supported; retain the old judge only as historical baseline evidence.

**Oracle Gate B6**

```bash
python -m arnold_pipelines.megaplan bakeoff run --idea-file <fixture> --profiles <omp-profile> <baseline-profile> --robustness light
python -m arnold_pipelines.megaplan bakeoff run --idea-file <fixture> --profiles <omp-profile> <baseline-profile> --robustness full
python -m pytest -q tests/bakeoff tests/arnold_pipelines/megaplan/test_omp_dispatch.py
```

Persisted comparison evidence must show no must-level regression.

## B7 — Resident omp backend and stateless session semantics

1. Update managed-agent backend registration, default models, capabilities, inference, and route resolution.

2. Update `ManagedProviderCliAgentRunner` and `_command` for omp RPC, tools, cwd, credentials, timeout, process group, and fresh stateless sessions.

3. Replace the Hermes evidence normalizer with `_normalize_omp`, including assistant text, tool events, usage, failures, normalized event files, and provider provenance.

4. Fix the newly discovered hard resident identity requirement. `_run_locked` asserts a resolved session identity on success, while the current omp path returns `None`/`False` from `reserve_session_id`/`valid_session_id`. Implement a synthetic per-turn marker such as `omp-stateless:<turn-id>`, accept it through the handshake, and explicitly skip session-file persistence and resume semantics for omp. Do not pretend the marker is a resumable omp session.

5. Update resident config and runtime model-seam metadata. Python composes the full hot context; omp receives no duplicated persisted context.

6. Add deterministic restart, retry, concurrent-session, duplicate-prompt, and one-turn success tests. The one-turn test must prove final text, evidence, usage, ledger shape, synthetic identity, and absence of a persisted omp session file.

**Oracle Gate B7**

```bash
python -m pytest -q \
  tests/resident/test_managed_provider_agent_runner.py \
  tests/resident/test_provider_runtime.py \
  tests/resident/test_context_tree.py \
  tests/resident/test_turn_handoff.py \
  tests/resident/test_omp_stateless_turn.py
```

The oracle checks the session identity fix, no duplicated context, correct store/manifest/ledger/evidence/notification shapes, and successful omp turn completion.

## B8 — RPC subagent fanout parity

1. Replace Hermes fanout with one `RpcClient` child per unit in resident subagent code, process fanout, and worker fanout. Default to shared cwd and no worktrees. Worktrees are opt-in only when an isolation request explicitly asks for them.

2. Replace the deprecated `parallel_critique._run_check` and any remaining AIAgent-constructed test/deprecated path with the RPC contract.

3. Preserve output order, timeout, cancellation, restart, manifest, ledger, delivery, and cleanup semantics. Do not use omp `task` as an implicit replacement.

4. Add final parity fixtures for success, timeout, pre-launch cancellation, mid-flight cancellation, partial failure, sibling continuation, submission order, cost aggregation, and child cleanup. Assert no orphaned `bun ... --mode rpc` child.

**Oracle Gate B8**

```bash
python -m pytest -q \
  tests/characterization/test_agent_fanout_boundaries.py \
  tests/resident/test_launch_subagent.py \
  tests/resident/test_subagent_restart_persistence.py \
  tests/arnold_pipelines/megaplan/test_worker_fanout_fallback.py
```

The oracle requires 1:1 RPC fanout, shared-cwd behavior, no implicit worktree, and parity for all listed fixtures.

## B9 — Cloud wrappers, watchdog, heartbeat, systemd, and Docker

1. Migrate every live wrapper and launcher, explicitly including the five additional surfaces discovered by U12:

   - `arnold-repair-loop`;
   - `arnold-kimi-goal-operator`;
   - `arnold-meta-repair-loop`;
   - `arnold-progress-auditor`;
   - `arnold-resident-schedule-run-once-r7`.

   Also migrate `arnold-watchdog`, `arnold-run`, `arnold-supervise`, `bakeoff/judge.py`, sibling wrappers, and `cloud/summarize_fixer_session.py`. Remove launcher defaults, fallback dispatch, `/root/.hermes` probes, Hermes skill sync, and `run_agent` paths.

2. Add `cloud.yaml.tmpl` and `simulate_watchdog_end_to_end.py` to the migration and fixture census.

3. Rewrite watchdog correlation around the real omp argv shape: `bun .../src/cli.ts --mode rpc --provider ... --model ... --session-dir ... --no-session`.

   - Add `pgid` to Python process records.
   - Parse `--session-dir`.
   - Correlate by process group, session directory, plan/attempt token, cwd, birth time, and heartbeat file.
   - Copy the existing `kimi_operator_running` pgid-sidecar and group-kill pattern.
   - Make bash classifiers recognize omp RPC argv as live and targetable.
   - Ensure parent termination kills the entire RPC process group.
   - Test orphan, PID reuse, stale heartbeat, wrapper restart, and false-positive cases.

4. Update `arnold-heartbeat` and `mp-heartbeat` to observe omp RPC activity and stale-heartbeat group death.

5. Update systemd units, entrypoint templates, bootstrap scripts, and service defaults. Remove Hermes auth/bootstrap state and change the resident service provider to omp with an exact `omp:<provider/modelId>` model.

6. Close the Dockerfile gap explicitly:

   - pin Bun at `>=1.3.14` to an exact chosen version;
   - add `/root/.bun/bin` to `PATH`;
   - install the pinned omp checkout or compiled binary;
   - install the pinned pure-Python `omp_rpc` package;
   - install the required Linux natives for the target architecture;
   - treat a missing Linux `.node` native as a hard failure, not a recoverable warning;
   - install the `omp` PATH launcher;
   - smoke-test Bun, omp RPC mode, `import omp_rpc`, native resolution, and launcher permissions from an empty cache.

**Oracle Gate B9**

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/*
bash -n arnold_pipelines/megaplan/cloud/systemd/*
python -m pytest -q \
  tests/cloud/test_watchdog_wrappers.py \
  tests/arnold_pipelines/megaplan/watchdog/test_liveness_correlation_authority.py \
  tests/cloud/test_cloud_dockerfile_tool_versions.py
rg -n 'hermes:|run_agent|launch_hermes|hermes_auth|\.hermes' \
  arnold_pipelines/megaplan/cloud agentbox
```

The oracle checks all five extra surfaces, `cloud.yaml.tmpl`, the simulator, real omp argv recognition, pgid/session-dir correlation, process-group kill, pinned Bun/PATH, installed omp/omp-rpc/natives, and generated deployment output.

## B10 — Agentbox staging, replay, fault injection, and green runs

1. Deploy the migrated resident to the actual agentbox/Hetzner path. Exercise normal Discord turns, tool turns, restart, concurrent messages, cancellation, timeout, and recovery.

2. Replay RPC transcripts across restart, retry, process kill, concurrent sessions, and duplicate prompt. Assert one intended context, no stale state, no duplicate execute, and no duplicate delivery.

3. Inject launch, EOF, malformed-frame, timeout, 429, 5xx, authentication, quota, context, and schema failures through resident and watchdog recovery.

4. Complete three consecutive green live phase runs and one green resident Discord run. Retain journals, manifests, ledgers, evidence, process trees, usage, and cost artifacts.

**Oracle Gate B10**

```bash
python -m pytest -q tests/resident tests/cloud tests/arnold_pipelines/megaplan/watchdog tests/fixer_replay
journalctl -u agentbox-discord-resident.service --since <run-start>
ps -eo pid,ppid,pgid,args
```

Any orphan, replay divergence, cost mismatch, wrong-tree write, or duplicate side effect loops to the responsible B7–B10 batch.

## B11 — Relocation-first Hermes deletion

1. Vendor the sandbox source of truth rather than rewiring imports. The exact primitive names are:

   `SANDBOX_CWD`, `SANDBOXED_EXEC_TOOLS`, `SANDBOXED_WRITE_TOOLS`, `SandboxViolation`, `get_sandbox_cwd`, `validate_terminal_command`, `validate_v4a_patch`, `validate_write_path`.

   Account explicitly for the six wrapper symbols:

   `install_sandbox`, `_unwrap_all_for_tests`, `_wrappers_installed`, `_wrappers_lock`, `_wrapped_originals`, `_WRAPPERS`.

   `SandboxViolation` must inherit from relocated `arnold.runtime.errors.ArnoldError`. The old tool-registry wiring behind `install_sandbox` is not a live production path; omp pre-exec validation replaces it.

2. Vendor the exact ten KeyPool names:

   `KeyEntry`, `KeyPool`, `minimax_openrouter_model`, `resolve_kimi_base_url`, `_DEFAULT_BASE_URLS`, `_ENV_ALIASES`, `_PROVIDER_BASE_URL_VARS`, `_PROVIDER_KEY_VARS`, `provider_credential_env_vars`, and `KeyPathSource`.

   Preserve governor/envelope charging. Port the transitive `_envelope_ctx` access from `arnold.runtime.envelope`. Remove Hermes home/env semantics and retain only neutral credential pooling.

3. Port all consumers, including resident runtime and agent loop, preflight, profiles/policy, cloud code, parallel-critique/review paths, and tests. No new runtime module may import `arnold.agent`.

4. Delete `workers/hermes.py`, Hermes fanout and launcher paths, `DeepSeekAdapter`, AIAgent runtime/tools, the old providers pool, SessionDB, cron/honcho/Hermes CLI paths, and implementation-internal tests. Remove Hermes dependencies/comments from `pyproject.toml`.

5. Validate fresh-venv import and cold-start before final cleanup.

**Oracle Gate B11**

```bash
rg -n 'from arnold\.agent\.tools|arnold\.agent\.providers\.pool|AIAgent|DeepSeekAdapter|workers\.hermes|launch_hermes|run_agent' arnold arnold_pipelines agentbox tests pyproject.toml
python -m compileall -q arnold arnold_pipelines agentbox
python -P -c "import arnold; import arnold_pipelines.megaplan; import arnold_pipelines.megaplan.runtime.sandbox; import arnold_pipelines.megaplan.runtime.key_pool"
python -m pytest --collect-only -q
```

The oracle requires no import-back edge, clean cold start, and successful neutral runtime imports.

## B12 — Resident-agent platform and Astrid

1. Add a resident generator under `arnold_pipelines/megaplan/resident/` and expose it through `resident/cli.py`. It must generate all four contracts:

   - domain agent prompt and tool restriction;
   - tool/permission, credential, and cwd policy;
   - session identity, persistence, recovery, and concurrency;
   - evidence/output normalization, supervision, heartbeat, and delivery.

2. Add `examples/agents/astrid-resident.md` plus Arnold-side domain configuration without modifying omp `src/`.

3. Implement the concrete Astrid resident contract:

   - attach to a project as `agent:<id>` and operate on `projects/<slug>/` and `runs/<slug>/`;
   - use the Astrid gateway, with `--engine arnold` when invoking the Arnold adapter;
   - repeatedly call `astrid next`; execute exactly the one legal action returned (`bootstrap`, `run: ...`, or `ack ...`);
   - never freelance actions outside the gateway’s returned command;
   - use `astrid status` to reorient after restart or uncertainty;
   - acknowledge human gates with the explicit approval/acknowledgement action;
   - on lease conflict, obey writer-epoch rules and perform takeover only through the supported session takeover protocol;
   - expose only Astrid gateway tools and file tools constrained to the run directory;
   - load provider credentials from the repository `.env.local`, including the documented OpenAI/Gemini/Anthropic/RunPod/Hugging Face/Replicate and Astrid-specific variables;
   - record typed media outputs such as `video/mp4`, `audio/wav`, and `x-astrid-timeline`;
   - emit typed media evidence plus `MediaUsage` cost into the resident store, manifest, ledger, notifications, heartbeat, watchdog, and restart-recovery paths.

4. Run one live Astrid end-to-end flow through attach → `astrid next` → gateway action → artifact → typed evidence → delivery.

5. Document the reusable generator/platform contract in `docs/agents.md` and test deterministic generation and project-over-user installation.

**Oracle Gate B12**

```bash
python -m pytest -q tests/resident/test_resident_generator.py tests/resident/test_astrid_resident.py
python -m arnold_pipelines.megaplan resident --help
```

The oracle inspects generated files and live Astrid evidence, including typed media and `MediaUsage`, not merely the final assistant message.

## B13 — Final release gate

1. Run the categorized acceptance scan over live source, config, deployment, generated artifacts, fixtures, and scripts:

   ```bash
   rg -n 'hermes:|arnold\.agent|run_agent|launch_hermes|hermes_auth|\.hermes' \
     arnold arnold_pipelines agentbox tests .github scripts pyproject.toml .env.example
   ```

2. Allow remaining hits only in the explicit historical allowlist: `.megaplan/**`, archived documents, and SOL/design/review artifacts. Every other hit is a release failure.

3. Re-run focused tests, fresh import/cold-start, fork diff, bakeoff evidence, resident replay, watchdog fault matrix, Docker smoke, and three-green-run evidence.

4. Produce the release manifest containing commit hash, omp fork hash, translation-table hash, test results, sandbox/trusted-container evidence, bakeoff comparison, fanout fixtures, session replay corpus, watchdog evidence, cost reconciliation, and historical-hit allowlist.

**Final Oracle Gate**

Accept only with zero live Hermes traces, no old imports, no stale deployment default, no fork `src/` delta, exact cost accounting, no orphan process, successful stateless resident turns, complete Astrid evidence, and no failed must criterion. A patch-only explanation never passes.

## Sequencing decision

B1–B13 remain in the same order. The evidence did not change the dependency graph:

- B1/B4 now use a final provider/model/credential/thinking table with no verification caveat and include the two U6 census additions.
- B2 now has the decided structured-file output path and final exactly-once cost reconciliation.
- B5 replaces the former bwrap requirement with the documented trusted-container decision and exact fork cleanup/cold-start rules.
- B7 gains the mandatory synthetic stateless session-identity fix and turn-level test.
- B8 records confirmed 1:1 shared-cwd fanout and complete parity fixtures.
- B9 expands the cloud census, adds real omp process correlation, and contains the complete Dockerfile install/smoke recipe.
- B11 makes relocation explicit vendoring with exact symbol lists and removes old tool-registry wiring.
- B12 embeds the concrete Astrid gateway, lease, tool, credential, and typed-media contract.
- B10 and B13 retain their position because operational proof must precede deletion and final acceptance.

## Final verdict: HOLISTIC / COMPLETE

The solidified list is holistic and complete for the stated goal: it covers phase workers, dispatch, credentials, structured output, cost, sandbox boundaries, resident semantics, session identity, fanout, cloud deployment, watchdog custody, deletion, fork cleanliness, platform generation, Astrid integration, and final zero-trace acceptance.

Remaining unknowns requiring exploration before execution: none. Any failure discovered during implementation is already assigned to an explicit task and oracle gate.

Final confidence: **94/100**.

Changed in this pass: all U1–U13 exploration results were folded into the executable batches and their gates, including the agentbox trusted-container decision, the resident identity blocker, the complete Docker/watchdog recipe, exact relocation scope, and the fully specified Astrid contract.
