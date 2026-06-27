# Tests

This tree mixes fast unit tests, structural contract tests, golden baselines,
agent-facing fixtures, and opt-in runtime tiers. Most fixture and baseline paths
are intentionally stable because tests, docs, and tools reference them directly.

## Layout

| Path | Purpose |
|---|---|
| `conftest.py` | Shared pytest hooks, known-failures handling, RunPod marker helpers, and collection behavior. |
| `test_*.py` | Flat feature-area tests for the package, CLI, porting, runtime, templates, and contracts. |
| `browser/` | JavaScript browser harness tests that exercise ComfyUI-facing surfaces. |
| `characterization/` | Deterministic golden-snapshot tests. Use `PYTHONHASHSEED=0` when running this tier directly. |
| `e2e/` | Real-browser Playwright specs and npm metadata. Local outputs are ignored. |
| `edgecases/` | Boundary, compatibility, concurrency, and failure-mode tests. |
| `fixtures/` | Authored JSON/session/source-code fixtures loaded by tests and tools. |
| `structural_harness/` | Deterministic structural contract harness: adapter, runner, builders, scenarios, and briefs. |
| `live_agentic_harness/` | True live-agentic harness placeholder; no fake builders or scripted scenarios. |
| `intent/` | Intent-level edit correctness, falsification, perceptual hash, and judge-evaluation tests. |
| `parity/` | Typed-handle parity and independent readback tests plus parity fixtures. |
| `property/` | Property-based and fuzz-style tests. |
| `security/` | Security gates for loaders, provenance, capabilities, and cross-layer boundaries. |
| `smoke/` | Opt-in GPU/RunPod smoke tests. |
| `smoke_fixtures/` | Lightweight smoke-test JSON inputs. |
| `snapshots/` | Committed API/class-type/widget baseline snapshots regenerated in place. |
| `support/` | Shared support utilities used across test modules. |

## Test taxonomy

The word **"agentic"** is overloaded in this repo. We use these categories:

| Category | Definition | Key locations |
|---|---|---|
| **Live agentic tests** | Run the real executor/agent path with **real model/provider calls**. Opt-in because they need credentials. | `tests/test_agentic_harness_live.py` — run with `--run-live` |
| **Structural agentic tests** | Run the **real executor/agent-edit path on real workflows**, but with scripted/fake model responses. They produce real compiled graphs and frozen evidence. | `tests/structural_harness/scenarios/*.yaml` and `tests/structural_harness/actors*.py` |
| **Headless harness contract tests** | Fake-backend tests proving the headless service and runner wire all the way through to `run_executor`. | `tests/test_headless_harness_contract.py`, `tests/test_headless_harness_runner_contract.py` |
| **Executor contract tests** | Deterministic phase-wiring tests for `classify → research → implement → reply`; models are mocked. | `tests/test_executor_flows.py`, `tests/test_executor_contracts.py` |
| **Agent-edit characterization tests** | DSL/session roundtrip invariants against real UI fixtures. | `tests/characterization/test_agent_edit_roundtrips.py` |
| **Browser/UI e2e tests** | Boot ComfyUI, load a real graph, submit a prompt, apply a candidate, and assert a real canvas change. Model response is fixture-backed. | `tests/e2e/specs/`, `agent_edit_e2e.mjs` |

So "agentic test" means: the real agent/executor workflow machinery is traversed on a real workflow. A live agentic test additionally calls a real model. A contract test only checks orchestration with mocks.

## Running

```bash
pytest tests/ -q
PYTHONHASHSEED=0 pytest tests/characterization/ -q
pytest --runpod tests/smoke/ -q
cd tests/e2e && npx playwright test
pytest --known-failures-audit -q

# Live agentic tests (real DeepSeek/OpenRouter calls; requires credentials)
pytest tests/test_agentic_harness_live.py --run-live -q -s

# Structural agentic scenarios (deterministic, real workflow edits)
python -m tests.structural_harness.runner --tag structural-run
python -m tests.structural_harness.runner --tag hotshot-run --name hotshot-16-frames-agent-edit
```

The full suite has known baseline failures in this checkout. Use focused tests
for structure-only changes, and use `--known-failures-audit` when changing test
names, paths, or baseline ownership.

## Quarantine Retirement

Scoped quarantine files live in `tests/quarantine/`. Each file must keep
`# owner:` and `# reason:` metadata, and every active non-comment line must be a
single pytest function nodeid. `tests/known_failures.txt` is legacy
documentation only; do not add active entries there.

To retire a quarantine entry:

1. Fix the underlying failure.
2. Remove the exact nodeid from the owning `tests/quarantine/*.txt` file.
3. Run the focused quarantine suite:

```bash
pytest tests/test_comfy_nodes_browser.py tests/test_quarantine_loader.py tests/test_quarantine_policy.py tests/characterization/test_known_failures_audit.py -q
```

4. Run the stale-entry audit before merging:

```bash
pytest --known-failures-audit -q
```

## Generated Baselines

Generated baselines under `tests/snapshots/`, `tests/characterization/goldens/`,
and `tests/fixtures/canonical_parity_baseline.json` are committed on purpose.
Regenerate them with their owning tools and commit the updated baselines
together with the source change that requires them.

Local browser outputs and dependencies are intentionally ignored:

- `tests/e2e/node_modules/`
- `tests/e2e/playwright-report/`
- `tests/e2e/test-results/`
