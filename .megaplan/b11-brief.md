# B11 — Hermes SDK deletion + neutral runtime vendoring (execution brief)

Repo: `/workspace/omp-replaces-hermes/Arnold`. Test interpreter:
`/workspace/omp-replaces-hermes/.venv/bin/python`. Do NOT run project-wide
test suites or formatters; run ONLY the exact commands listed.

## Goal

Delete the Hermes agent SDK from `arnold/agent/` and vendor the two
still-needed surfaces into the neutral megaplan runtime so no live module
imports `arnold.agent` (the B13 release scan `arnold\.agent` must be clean).
Preserve every behavior the passing tests rely on.

## Step 1 — Vendor the sandbox (neutral runtime)

`arnold_pipelines/megaplan/runtime/sandbox.py` currently re-exports from
`arnold.agent.tools.sandbox` and `arnold.agent.tools._sandbox_wrappers`.
Replace it with a SELF-CONTAINED vendored copy of BOTH source modules'
content (copy the code, adapt imports):

- Primitives (exact names): `SANDBOX_CWD`, `SANDBOXED_EXEC_TOOLS`,
  `SANDBOXED_WRITE_TOOLS`, `SandboxViolation`, `get_sandbox_cwd`,
  `validate_terminal_command`, `validate_v4a_patch`, `validate_write_path`.
- Wrapper machinery (exact names): `install_sandbox`, `_unwrap_all_for_tests`,
  `_wrappers_installed`, `_wrappers_lock`, `_wrapped_originals`, `_WRAPPERS`.
- `SandboxViolation` MUST inherit from `arnold.runtime.errors.ArnoldError`
  (relocate the base class if needed; check `arnold/runtime/errors.py`).
- Keep the module docstring's semantics; the ContextVar identity must be
  preserved (a single `SANDBOX_CWD` object).

## Step 2 — Vendor the KeyPool (neutral runtime)

`arnold_pipelines/megaplan/runtime/key_pool.py` currently inherits/re-exports
from `arnold.agent.providers.pool`. Vendor the pool's content so it is
self-contained and imports ONLY neutral modules (`arnold.runtime.envelope`,
megaplan runtime governor/types). Required public names (exact):
`KeyEntry`, `KeyPool`, `minimax_openrouter_model`, `resolve_kimi_base_url`,
`_DEFAULT_BASE_URLS`, `_ENV_ALIASES`, `_PROVIDER_BASE_URL_VARS`,
`_PROVIDER_KEY_VARS`, `provider_credential_env_vars`, `KeyPathSource`.
Preserve governor/envelope charging and the `_envelope_ctx` access.
Keep the existing megaplan-specific helpers (`acquire_key`, `resolve_model`,
etc.) working.

## Step 3 — Relocate the neutral contracts + routing

`arnold/agent/contracts.py` (AgentSpec/AgentMode/AgentRequest/AgentResult/
CostUsage/FanoutResult/parse_agent_spec/format_agent_spec/etc.) and
`arnold/agent/routing.py` (managed-agent routing) are NEUTRAL and load-bearing.
Move them OUT of `arnold/agent/` — recommended target
`arnold/runtime/agent_contracts.py` and `arnold/runtime/agent_routing.py` —
and update every importer. 32 files import them (list: run
`grep -rln 'from arnold\.agent\.contracts\|from arnold\.agent\.routing' arnold arnold_pipelines agentbox tests --include='*.py'` and update each, excluding `arnold/agent/` itself). Keep the public names identical so
importers can be changed with a simple module-path substitution.

## Step 4 — Port remaining live SDK edges

- `arnold_pipelines/megaplan/workers/_impl.py`:
  - `_is_agent_available(agent)`: the `agent == "hermes"` branch probes the
    vendored `run_agent`/`hermes_state` modules. Post-migration "hermes"
    agent specs are no longer a live dispatch surface (omp replaced it);
    make the hermes branch report availability via the omp CLI (`shutil.which
    "omp"`) or route hermes specs to omp availability, matching the B3
    dispatch contract. Keep `_is_agent_available("codex")` / `("claude")`
    unchanged.
  - The `MEGAPLAN_USE_AGENT_DISPATCHER=1` flag-ON path (around line 7725):
    it imports `ArnoldDispatcher`, `DeepSeekAdapter`, and
    `arnold.agent.contracts.AgentRequest`. Rework it so it does NOT import
    from `arnold.agent`: the dispatcher/contracts come from the relocated
    modules, and the `"hermes"` registration routes through the omp adapter
    (`_omp_to_agent_result`) instead of `DeepSeekAdapter` (delete the
    DeepSeekAdapter registration). The existing B3 tests
    (tests/arnold_pipelines/megaplan/test_omp_dispatch.py) must still pass in
    both dispatch modes.
- `arnold_pipelines/megaplan/agent/minisweagent_path.py` and
  `arnold_pipelines/megaplan/agent/tools/terminal_tool.py` import from
  `arnold.agent.*` — vendor or relocate the tiny bits they use, or delete the
  files if they are dead (check importers).
- `arnold_pipelines/megaplan/agent_adapters/*` import
  `arnold.agent.contracts` — update to the relocated module.
- `arnold/execution/registries.py` — update the contracts import.

## Step 5 — Delete the SDK

Delete (git rm):
- `arnold_pipelines/megaplan/workers/hermes.py`
- The `arnold/agent/` directory EXCEPT nothing (all of it: `__init__.py`,
  `contracts.py`, `routing.py`, `adapters/`, `agent/`, `costing/`, `cron/`,
  `dispatcher.py`, `hermes_cli/`, `hermes_constants.py`, `hermes_state.py`,
  `hermes_time.py`, `honcho_integration/`, `minisweagent_path.py`,
  `model_tools.py`, `providers/`, `run_agent.py`, `tools/`)
- `arnold_pipelines/megaplan/agent/` if it becomes fully dead after porting.
- Remove Hermes dependencies/comments from `pyproject.toml` (the
  "Hermes/agent backend (core)" comment block and any hermes-only deps).
- Remove `launch_hermes_agent.py` references in skills if the file is part
  of the SDK (check `arnold_pipelines/megaplan/skills/subagent-launcher/`).

After deletion, `rg -n 'arnold\.agent' arnold arnold_pipelines agentbox tests
--include='*.py'` must be empty (excluding pyc).

## Step 6 — Gate verification (run these EXACTLY)

```bash
cd /workspace/omp-replaces-hermes/Arnold
rg -n 'from arnold\.agent\.tools|arnold\.agent\.providers\.pool|AIAgent|DeepSeekAdapter|workers\.hermes|launch_hermes|run_agent' arnold arnold_pipelines agentbox tests pyproject.toml
# expect ZERO hits
/workspace/omp-replaces-hermes/.venv/bin/python -m compileall -q arnold arnold_pipelines agentbox
/workspace/omp-replaces-hermes/.venv/bin/python -P -c "import arnold; import arnold_pipelines.megaplan; import arnold_pipelines.megaplan.runtime.sandbox; import arnold_pipelines.megaplan.runtime.key_pool"
/workspace/omp-replaces-hermes/.venv/bin/python -m pytest --collect-only -q
```

Then run these targeted suites (they exercise the ported surfaces):
```bash
/workspace/omp-replaces-hermes/.venv/bin/python -m pytest -q \
  tests/arnold_pipelines/megaplan/test_omp_dispatch.py \
  tests/arnold_pipelines/megaplan/test_model_seam_recovery.py \
  tests/arnold_pipelines/megaplan/test_provider_contract_failure_routing.py \
  tests/workers/test_omp_adapter.py \
  tests/arnold/agent/ \
  tests/resident/test_omp_stateless_turn.py \
  tests/arnold_pipelines/megaplan/runtime/
```
Fix any failures these expose (they are load-bearing contracts, not tests to
weaken). Also run
`/workspace/omp-replaces-hermes/.venv/bin/python -m pytest -q tests/sandbox/test_omp_sandbox.py`
(uses the vendored sandbox).

## Constraints

- Do NOT modify omp (`/workspace/omp-replaces-hermes/oh-my-pi`).
- Do NOT run project-wide pytest. Target the listed commands only.
- Do NOT commit. Leave changes in the working tree for the orchestrator.
- If a deletion breaks an import you cannot resolve cleanly, STOP and report
  the exact failure rather than hacking around it.
- Preserve the frozen omp grammar and the B3 dispatch contract.

Report: what you vendored/relocated/deleted, the gate command outputs, the
targeted test results, and any remaining `arnold.agent` references with
explanations.
