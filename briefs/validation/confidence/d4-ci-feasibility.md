## Verdict: Yes — but CI needs surgery to make it real

### 1. CI test selection (`ci.yml:21`)

CI runs a **hardcoded named-file list** — not discovery:

```
pytest tests/characterization/test_import_surface.py tests/test_pipeline_run_cli.py tests/test_cloud_template.py tests/test_cloud_spec.py -q
```

Only 4 files out of 50. The parity gate (`test_pipeline_parity.py`), chain-status contracts (`test_cloud_chain_status.py`), and every other contract test are simply **never invoked**. To add enforcement, you must either add filenames to the list or switch to discovery with markers (`-m "not slow and not docker"`).

### 2. Parity gate runs fully hermetic ✅

`test_pipeline_parity.py:164` consumes `bootstrap_fixture` (`conftest.py:140–166`), which sets `MEGAPLAN_MOCK_WORKERS=1` and monkeypatches `shutil.which` to return `/usr/bin/mock` for `claude`/`codex`. **Zero API keys, zero network, zero external processes.** The mock payloads are deterministic (`_build_mock_payload`). It will run in CI exactly as it runs locally. No blockers.

### 3. Blast-radius tests with zero CI enforcement

| Test file | Why skipped / absent |
|---|---|
| `test_cloud_docker_build.py` | Module-level `pytest.skip("docker not available")` (`:19–21`); separate `docker-test` job with `continue-on-error: true` (`ci.yml:36`) — advisory, not enforcement |
| `test_cloud_deploy_smoke.py` | `requires_docker` fixture skip (`:22–42`) |
| `test_cloud_local_lifecycle.py` | Module-level docker skip (`:23–36`) |
| `test_workers_tmux.py` | `@pytest.mark.skipif(shutil.which("tmux") is None)` on every test (`:18`) |
| `test_cloud_chain_status.py` | Not in named list (1932-line contract test — zero CI coverage) |
| `editorial_gating.py`, `test_resolutions.py`, `test_quality.py`, `test_review_checks.py`, etc. | Not in named list |

These paths have **zero enforcement on PRs**. Docker tests are best-effort with `continue-on-error` — a failure turns the job green.

### 4. Cassette/VCR infra: **does not exist**

Zero `vcrpy`, `betamax`, or HTTP-recording infrastructure anywhere. The word "recording" in `test_epic_blitz_e2e.py:30` refers to a mock worker with tracked calls, not HTTP replay. No path exists today to test real-prompt shape without live API keys. This is a build-it-from-scratch milestone.

### 5. Duration / flakiness

Current CI runs 4 fast unit files (<30s). Three `@pytest.mark.slow` markers exist (`pyproject.toml:69`), all on Docker tests. No flaky markers. The parity gate itself is fast (mock workers, no I/O) and deterministic.

---

## Concrete plan

**ci.yml change** — replace the named-file line:

```yaml
run: pytest -m "not slow" -q
```

This runs everything hermetic (mock workers, no docker) on every PR, including the parity gate + chain-status + editorial gating + resolutions. Then keep `docker-test` as a separate `continue-on-error` advisory job with `-m slow`.

**Milestone ordering**: (A) Switch CI to marker-based discovery immediately — unlocks parity gate + contract enforcement. (B) Add `vcrpy` cassette infra as a separate milestone for prompt-assembly/cost-shape smoke without live keys. Severity: the gap is **high** — 92% of the test suite (46/50 files) has no CI enforcement today.