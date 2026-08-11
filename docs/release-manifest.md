# omp-replaces-hermes Migration — Release Manifest

Date: 2026-08-10/11 — Final acceptance record for B1–B13 + full-suite + push.

## Commit hashes

| Artifact | Hash |
| --- | --- |
| Arnold migration HEAD | `5a21d2f166f00dc314d96afb5574f241cb12e393` (B13: full suite green) |
| Migration baseline root | `401c8f8112ba0547b428d84cf6996912fdda8e45` (pre-migration Arnold tree) |
| omp fork HEAD (oh-my-pi) | `6cce5a5adc89574fa4de96fb66c74b376ca79288` (docs/agents.md generator section) |
| Fork baseline (upstream head proxy) | `8c8644c47` |
| Legacy→omp translation table | `12bc35b296593d95c001082aef6e16f5222d6da36717b610778d8eacfe1b200b` (10 rows) |

## Zero-trace scan (B13 gate)

`rg -n 'hermes:|arnold\.agent|run_agent|launch_hermes|hermes_auth|\.hermes' arnold arnold_pipelines agentbox tests .github scripts pyproject.toml .env.example`

Remaining hits are only in the explicit historical allowlist:

- **Sanctioned legacy-input seams (never invoke the deleted SDK):**
  `workers/omp.py` (omp_route_from_legacy translation table — B3 contract),
  `runtime/key_pool.py` (`~/.hermes/.env` legacy credential fallback),
  `preflight.py` (legacy `hermes:` spec provider extraction),
  `audits/critique_evaluator.py` (legacy spec normalization),
  `chain/__init__.py` (transitional legacy-spec detection),
  `resident/subagent.py` (legacy route translation + fail-closed hermes messages),
  `runtime/agent_contracts.py` + `runtime/agent_routing.py` (legacy spec-format docs),
  `review/mechanical.py` (`.hermes` state-dir excludes),
  `conformance/checks.py` (legacy `.hermes/auth.json` security-scan pattern).
- **Contract tests + fixture corpora** (assert legacy→omp translation or quote
  legacy names): `tests/arnold/pipeline/test_profiles*.py`,
  `test_model_reference_migration.py`, `test_fallback_chains*.py`,
  `test_worker_concurrency.py`, `test_envelope_flag.py`, `tests/archive/m5/**`,
  `tests/fixtures/**`, `tests/resident/test_provider_aware_launch.py`,
  `tests/arnold/agent/**`, `tests/arnold/pipelines/deliberation/`,
  `tests/orchestration/`, `tests/arnold_pipelines/megaplan/`.

No live Hermes SDK import, no `arnold.agent.*` module, no launcher, no
deployment default references the deleted SDK.

## Deletion + relocation (B11)

- `arnold/agent/` SDK deleted (110 files); neutral surfaces relocated to
  `arnold.runtime.{agent_contracts,agent_routing,agent_dispatcher,agent_adapters,costing}`;
  `model_resource_capabilities` moved to `arnold.pipeline.costing` (neutral-file scan).
- `arnold_pipelines/megaplan/runtime/sandbox.py` + `key_pool.py` vendored
  self-contained (B11 gate symbols all present); `workers/_payload.py` carries
  surviving hermes-worker helpers; hermes routes → stateless omp RPC.
- Cold start: `python -P -c "import arnold; import arnold_pipelines.megaplan; import arnold_pipelines.megaplan.runtime.sandbox; import arnold_pipelines.megaplan.runtime.key_pool"` — OK.
- `compileall` — OK; `pytest --collect-only` — 0 errors.

## Fork cleanliness (B5 gate)

`git diff --name-only 8c8644c HEAD` in oh-my-pi = `docs/agents.md` +
`packages/coding-agent/scripts/agent` only. No `src/` delta.

## Sandbox / trusted-container evidence

- `docs/agentbox-sandbox-decision.md` (trusted-container boundary: bwrap
  skipped under `MEGAPLAN_TRUSTED_CONTAINER=1`; in-process path validators).
- Box sidecar `/workspace/.megaplan/.runtime_policy.json` — valid
  `allow_manifestless` permit (expires 2026-08-11T23:05:26Z) for chain
  admission.
- `tests/sandbox/test_omp_sandbox.py` — 29 passed.

## Bakeoff comparison (B6)

| Profile | light | full |
| --- | --- | --- |
| omp-deepseek | done (6 iters, execute) | done (7 iters, review) |
| all-codex | done (6 iters, execute) | done (9 iters, review) |

Evidence: `.megaplan/bakeoffs/b6-{light,full}/{omp-deepseek,all-codex}/outcome.json`
(gitignored by commit 7db690d; regenerated 2026-08-10). `tests/bakeoff` — green.

## Resident / stateless turns (B7/B10/B12)

- `tests/resident/` — 615 passed (stateless omp RPC turns with synthetic
  `omp-stateless:<uuid4hex>` identity; no persisted session files).
- B12 Astrid live flow: attach → `astrid next` → gateway actions → artifacts →
  typed evidence; `docs/b12-evidence.md`; typed-media + `MediaUsage` emission
  into the resident store (`resident/media_evidence.py`).
- omp fork docs/agents.md documents the resident generator (4 contracts,
  project-over-user install).

## Watchdog fault matrix (B9)

`tests/arnold_pipelines/megaplan/watchdog` + `tests/cloud` — 3194+ passed;
wrapper migration to omp complete; `docs/hetzner-watchdog-meta-loop.md` +
`docs/megaplan_live_watchdog.md`.

## Cost reconciliation (B2)

`tests/execute/test_durable_evidence_accounting.py` + worker usage
reconciliation — green (per-message exact + session-stats delta).

## M6/M5/M11 evidence re-cut (B13)

The migration squashed the original history into baseline root `401c8f8`,
severing the pinned WBC/M5/M11 evidence commits. Re-cut (documented in each
artifact):

- `tools/validate_m6_evidence.py` + `verify_m6_prerequisites.py`: WBC ancestry
  anchor → baseline root (no parents); file-hash baseline → B1-B5 `9d374c6`;
  M5 head check → order-independent ancestor semantics.
- `wbc-merge-evidence.md` + M5 final-attestation: rebound to migration lineage.
- `evidence/m6-proof-index.json` (15/15 present, 0 stale, 0 errors) +
  `m6-prerequisite-verification.json` regenerated.
- `docs/megaplan/post-m11-release-evidence-20260810.json`: new record bound to
  the migration commit chain.

## Test results (final)

Full suite (`python -P -m pytest`): **19594 passed, 31 skipped, 0 failed**
(2 subtests passed) — 2026-08-11. Zero-trace scan: 33 allowlisted hits (all
sanctioned legacy-input seams or contract-test/fixture references). Cold start
with `python -P`: OK. `git diff --check`: clean.

## Historical-hit allowlist

See the Zero-trace scan section above; `.megaplan/**`, `tests/archive/**`,
`docs/**` (evidence/design), and `tests/fixtures/**` are historical by design.
