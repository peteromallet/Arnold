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
| `intent/` | Intent-level edit correctness, falsification, perceptual hash, and judge-evaluation tests. |
| `parity/` | Typed-handle parity and independent readback tests plus parity fixtures. |
| `property/` | Property-based and fuzz-style tests. |
| `security/` | Security gates for loaders, provenance, capabilities, and cross-layer boundaries. |
| `smoke/` | Opt-in GPU/RunPod smoke tests. |
| `smoke_fixtures/` | Lightweight smoke-test JSON inputs. |
| `snapshots/` | Committed API/class-type/widget baseline snapshots regenerated in place. |
| `support/` | Shared support utilities used across test modules. |

## Running

```bash
pytest tests/ -q
PYTHONHASHSEED=0 pytest tests/characterization/ -q
pytest --runpod tests/smoke/ -q
cd tests/e2e && npx playwright test
pytest --known-failures-audit -q
```

The full suite has known baseline failures in this checkout. Use focused tests
for structure-only changes, and use `--known-failures-audit` when changing test
names, paths, or baseline ownership.

## Generated Baselines

Generated baselines under `tests/snapshots/`, `tests/characterization/goldens/`,
and `tests/fixtures/canonical_parity_baseline.json` are committed on purpose.
Regenerate them with their owning tools and commit the updated baselines
together with the source change that requires them.

Local browser outputs and dependencies are intentionally ignored:

- `tests/e2e/node_modules/`
- `tests/e2e/playwright-report/`
- `tests/e2e/test-results/`
