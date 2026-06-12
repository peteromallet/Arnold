# Brief A — Internal testing excellence

`all-claude / standard`

## Why this sprint exists

VibeComfy has a solid testing instinct (~797 fast unit tests, opt-in RunPod smoke, two-level GPU gate) but several systemic gaps mean the suite isn't actually doing the job it could:

1. **15 pre-existing test failures** sit in the suite (9 schema-snapshot variants, 5 porting-convert parity, 1 contract-doctor diagnostic). A separate tactical agent is fixing the most egregious ones in parallel — assume those are landing, but the *systemic* causes (e.g. `LocalSchemaProvider` not extracting output specs, snapshots being hand-curated with no regen tooling) are this sprint's scope.
2. **No CI.** `.github/workflows/` doesn't exist. The 6-second suite isn't gating anything.
3. **No coverage signal.** No `pytest-cov`, no `.coveragerc`. ~17 k LOC of source can't say what's untested. Several `untested_module` mechanical findings exist (`router_rules.py`, `patches/gguf_unet.py`, `runtime/server.py`, etc.) with no programmatic way to confirm.
4. **Snapshots are write-once, never-regenerated.** `tests/snapshots/*.api.json` — 27 files across 9 templates — get edited by hand. When nodes legitimately change, the test fails forever or someone hand-edits JSON.
5. **God-test files.** `tests/test_runtime_session.py` (1985 LOC) and `tests/test_cli.py` (1254 LOC) mirror the god-source they test. Hard to read, hard to extend.
6. **Test-seam-only private function.** `vibecomfy/commands/doctor.py::_read_doctor_lockfile` is a one-line passthrough that exists only to be monkeypatched by `tests/test_doctor_lockfile.py`. It's dead weight.
7. **No cost cap on RunPod tests.** Per-pod timeouts exist (up to 3600 s) but no aggregate-cost cap. The `--runpod-full` marker says "~$5–10 per run" — that's a verbal contract, not a guard.
8. **No flake retry policy.** Smoke tests depend on real pod provisioning; one network blip becomes "is the test broken?" each time.

## What success looks like

Hard criteria, all measurable:

- [ ] **CI runs on every push and PR.** A GitHub Actions workflow that runs `uv sync && uv run pytest -q --tb=no` on Linux (Python 3.11). Wall time < 60 s. Status checks block merge to main.
- [ ] **Coverage gate ≥ 70 %.** `pytest-cov` added, configured to measure `vibecomfy/`. Baseline gate set permissively (70 %) so the team can lift it deliberately. CI surfaces a coverage diff comment on PRs (or at minimum a summary line in the job log). Untested-module list visible.
- [ ] **Snapshots regenerable.** `scripts/regenerate_snapshots.py` rebuilds every `tests/snapshots/*.api.json`, `*.class_types.json`, `*.widget_values.json` from current ready-template state. CI also runs `python scripts/regenerate_snapshots.py --check` and fails if snapshots are out of date *unless* the PR explicitly mentions snapshot changes (use a `snapshots:` commit tag or label).
- [ ] **Schema output extraction.** `vibecomfy/schema/provider.py::LocalSchemaProvider` (or its construction site) extracts output type specs from snapshot data, not just inputs. The 9 `test_snapshot_api_workflows_validate_against_permissive_local_schema` failures resolve as a side effect. Verify by running that test paramset under the CI suite.
- [ ] **`test_runtime_session.py` split into 3–5 focused files** that mirror behavior groups: config / lifecycle, embedded session, server session, run-untracked, validation. Each file < 700 LOC. No test logic changed; pure relocation. Test count stays the same.
- [ ] **`test_cli.py` split by command group** (sources/workflows/nodes, port, doctor/contract/validate, run/runtime, models/fetch, etc.). Each file < 500 LOC.
- [ ] **`_read_doctor_lockfile` deleted.** Patch sites in `tests/test_doctor_lockfile.py`, `tests/test_cli.py`, `tests/test_doctor_models.py` rewired to monkeypatch `vibecomfy.node_packs.read_lockfile` directly. No behaviour change.
- [ ] **RunPod cost cap.** New env var `VIBECOMFY_RUNPOD_BUDGET_USD` honored by `tests/smoke/_runpod_helpers.py`. When the cumulative *estimated* pod-hours × hourly rate for a single pytest invocation exceeds the budget, the next pod-provisioning call refuses (raises a clear test-failure with the running tally). Default budget: $2.00 for `--runpod`, $15.00 for `--runpod-full`. Hourly rate read from a small per-GPU-type table in the helpers module.
- [ ] **Flaky-retry policy.** `pytest-rerunfailures` added. Policy: tests marked `runpod` or `runpod_full` retry once on failure; nothing else retries. Encode in `pyproject.toml` or `conftest.py`.
- [ ] **Nightly RunPod smoke job.** GitHub Actions scheduled (`cron: '0 5 * * *'` UTC, i.e. ~midnight ET) that runs `uv run pytest --runpod tests/smoke/test_p1_runpod.py` against one cheap pod with `VIBECOMFY_RUNPOD_BUDGET_USD=2`. Requires `RUNPOD_API_KEY` and `VIBECOMFY_RUNPOD_STORAGE` as repo secrets. Sends a failure notification (annotate the workflow run; GitHub's default email-on-failure suffices unless the team has a Slack hook).
- [ ] **Suite is green at the end.** Zero `failed`, zero `xfailed` that's actually broken. `xfail` is allowed only for genuinely-pending features with a comment naming the issue.

## What's already known about the codebase

Recent commits on the branch `desloppify/strict-score-push` (active when this sprint starts):

- `desloppify: dedupe _node helper and tighten API surface` — moved `_node` into `vibecomfy/registry/ready_template.py`; updated 61 ready templates and the emitter
- `desloppify: remove back-compat aliases, convert tombstone, annotate loaders`
- `desloppify: extract shared ops helpers to _common module`
- `desloppify: fix run --ready drop, rename private helper, dedup URL stripper`

A separate fix-tests agent is also running and will land:

- A fix for the 9 `test_snapshot_api_workflows_validate_against_permissive_local_schema` failures — likely by teaching `LocalSchemaProvider` to consume output specs from `.class_types.json`/`.api.json` snapshots
- A fix for the 1 `test_ready_templates_contract_doctor_no_error_diagnostics` failure — by adding `sageattention` to `runtime_packages` in `ready_templates/video/ltx2_3_lightricks_first_last_two_stage_lowvram.py`
- Likely fixes for the 5 `tests/test_porting_convert.py` failures

If those fixes are in, the snapshot-extraction work in this sprint becomes the *durable* version of that tactical fix (regen tool + CI guard), not a re-fix.

## Files most likely involved

```
vibecomfy/schema/provider.py
vibecomfy/schema/cache.py
vibecomfy/commands/doctor.py            # _read_doctor_lockfile deletion
vibecomfy/node_packs/_lockfile.py       # canonical read_lockfile
tests/conftest.py                       # add coverage opts, rerun policy
tests/smoke/_runpod_helpers.py          # budget cap
tests/test_runtime_session.py           # split into 3–5
tests/test_cli.py                       # split by command group
tests/test_doctor_lockfile.py           # rewire patches
tests/test_doctor_models.py             # rewire patches
tests/snapshots/                        # regen target
pyproject.toml                          # pytest-cov, pytest-rerunfailures, coverage thresholds
scripts/regenerate_snapshots.py         # NEW
.github/workflows/ci.yml                # NEW
.github/workflows/nightly-runpod.yml    # NEW
docs/testing/overview.md                # NEW or updated, describes the contract
```

## Constraints and non-goals

- **Don't touch CLAUDE.md.** Project conventions there are stable.
- **Don't expand existing test coverage** beyond what's needed to keep the suite green during refactors. New unit tests aren't this sprint's job; visibility into what's untested is.
- **Don't add a coverage *target* above 70 %.** The point is making coverage visible, not gaming a number. Teams lift it once they can see it.
- **Don't introduce pytest-xdist.** 6-second suite doesn't need parallelism.
- **Vendor preference is `all-claude` (single-vendor Claude end-to-end at default effort).** No vendor swapping mid-sprint.

## Definition of done

```bash
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy
uv run pytest -q --tb=no               # exits 0
uv run pytest --cov=vibecomfy -q       # reports coverage; gate ≥70 %
python scripts/regenerate_snapshots.py --check   # exits 0 against committed snapshots
gh workflow view ci.yml                # exists
gh workflow view nightly-runpod.yml    # exists
```

And the file sizes for `test_runtime_session.py` and `test_cli.py` are gone (replaced by smaller siblings).
