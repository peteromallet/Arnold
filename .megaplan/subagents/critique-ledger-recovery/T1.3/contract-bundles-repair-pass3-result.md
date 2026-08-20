# T1.3 contract-bundle repair pass 3 — implementation result

## Result

Implemented and committed the bounded pass-3 repair in the required clean worktree.

- Base: `ddb764b30cedf3774ff5ca665a85a62090607b21`
- Commit: `fe1786c298361454a73754536ecf7de2f7b4bd69`
- Tree: `f11e71c1bbd6823a80bcba48c7bf88f655f44b8f`
- Branch: `fix/critique-recovery-contract-bundles-20260802`
- Worktree: `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`
- Worktree status after commit: clean

This is an implementation handoff, not a formal completion claim. A fresh independent Luna review and release-owner/integration evidence remain required by the brief.

## What changed

1. Added the policy-neutral `arnold.pipeline.contract_bundles` authority. It has no `arnold_pipelines` import and owns:
   - immutable provider transcript bytes/digest plus exact provider, model, tool, session, attempt, worker-channel, auth-channel, and capture-channel metadata;
   - the sole strict provider parser for Hermes, Shannon, Codex, and Claude routes;
   - duplicate-key, non-finite, invalid UTF-8, truncation, prose, ambiguous/multiple Shannon terminal-frame, and unsupported-route rejection;
   - shared immutable contract outcome, health, and binding types;
   - a frozen registry/binder/repair/preflight authority object.
2. Converted the Megaplan contract-bundle module into a compatibility/policy adapter around the neutral authority. Production admission calls the captured authority. Registry resolution, manifest loading, parsing, binding dependencies, validation, repair, and preflight dependencies are captured so compatibility rebinding cannot select a second authority; parser replacement fails closed.
3. Made `provider_transcript` the only production parser input. Hermes, Shannon, Codex, `WorkerResult`, and one-shot adapter metadata propagate the selected untouched response/frame. Critique and finalize preserve that transcript to a `.raw` evidence artifact before admission, including failure paths. Scratch content, `capture_output`, normalized payloads, reconstructed JSON, and legacy envelopes no longer mint acceptance.
4. Added realistic Hermes and Shannon provider fixtures, including strict Shannon event-stream framing, and packaged `.jsonl` fixtures in wheels. All four manifests now pin the neutral authority, parser/capture identities, current executable artifacts, and fixtures by digest.
5. Added neutral-core, compatibility, producer-fixture, disagreement, framing, metadata drift, response-loss, alternate-path/bypass, fresh-process rebind, immutable-type, and installed/source parity coverage.

## Files in the commit

- `arnold/pipeline/contract_bundles.py`
- `arnold_pipelines/megaplan/agent_adapters/_oneshot.py`
- `arnold_pipelines/megaplan/contract_bundles/__init__.py`
- `arnold_pipelines/megaplan/contract_bundles/critique_prompt_only_v1.json`
- `arnold_pipelines/megaplan/contract_bundles/critique_tool_enabled_v1.json`
- `arnold_pipelines/megaplan/contract_bundles/finalize_prompt_only_v1.json`
- `arnold_pipelines/megaplan/contract_bundles/finalize_tool_enabled_v1.json`
- `arnold_pipelines/megaplan/contract_bundles/fixtures/hermes_critique_response.json`
- `arnold_pipelines/megaplan/contract_bundles/fixtures/shannon_critique_response.jsonl`
- `arnold_pipelines/megaplan/handlers/finalize.py`
- `arnold_pipelines/megaplan/orchestration/critique_runtime.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- `arnold_pipelines/megaplan/workers/hermes.py`
- `arnold_pipelines/megaplan/workers/shannon.py`
- `pyproject.toml`
- `tests/arnold/pipeline/test_contract_bundles.py`
- `tests/arnold_pipelines/megaplan/test_contract_bundles.py`

## Validation evidence

Final affected/dependency matrix, after the last authority-capture hardening:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/arnold/pipeline/test_contract_bundles.py \
  tests/arnold_pipelines/megaplan/test_contract_bundles.py \
  tests/orchestration/test_critique_custody.py \
  tests/orchestration/test_parallel_critique.py \
  tests/arnold_pipelines/megaplan/test_m8a_finalize_wiring.py \
  tests/arnold_pipelines/megaplan/test_model_seam_recovery.py \
  tests/arnold_pipelines/megaplan/test_phase_wbc_resume_lifecycle.py

116 passed in 2.78s
```

Final producer/adapter matrix:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/test_workers_shannon_session.py \
  tests/test_shannon_adapter.py \
  tests/test_codex_adapter.py \
  tests/workers/test_hermes_execute_recovery.py \
  tests/workers/test_hermes_tool_markup.py \
  tests/workers/test_hermes_double_encoded_json.py \
  tests/orchestration/test_codex_output_schema.py

48 passed in 0.29s
```

Single-flight broad matrix:

```text
TMPDIR=/tmp/arnold-t13-pass3-broad PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest -p no:cacheprovider -q tests/arnold_pipelines/megaplan tests/orchestration

6721 passed, 8 failed, 25 warnings, 2 subtests passed in 521.18s
```

The eight broad failures were outside the changed boundary:

- The same five `tests/arnold_pipelines/megaplan/test_cloud_quickstart.py` tests reported by pass 2, all unable to infer a git origin in disposable repositories:
  - `test_cloud_quickstart_generates_canonical_initiative_from_one_brief`
  - `test_cloud_quickstart_stdout_is_single_json_payload`
  - `test_cloud_quickstart_can_infer_extra_repo_workspace_from_role`
  - `test_cloud_quickstart_extra_repo_supports_branch_and_workspace_override`
  - `test_cloud_quickstart_extra_repo_keeps_legacy_url_workspace_form`
- The same pre-existing M6 failure reported by pass 2: `tests/arnold_pipelines/megaplan/test_m6_evidence_validation.py::TestArtifactEntries::test_content_hashes_match_disk`, where `wbc_boundary_discovery_rules` stores `c207e8dc...` but disk hashes to `22d27065...`. A focused reproduction produced `41 passed, 1 failed`; neither that test nor the cloud quickstart test file differs from the required base.
- Two `tests/arnold_pipelines/megaplan/test_wheel_smoke.py::TestWheelSmoke` full-dependency installs exhausted the volume with `No space left on device`:
  - `test_wheel_installs_and_imports_product_package`
  - `test_cli_projection_imports_in_wheel`

The reproducible wheel proof was therefore also run separately without dependency duplication. The final tree built `arnold-0.23.0-py3-none-any.whl`, installed it into a fresh `--system-site-packages` venv with `--no-deps`, proved source/installed semantic parity for bundle help, registry signature, preflight, neutral type ownership, and the recorded Shannon fixture, and confirmed that the wheel contains the neutral core, manifests, Hermes JSON fixture, and Shannon JSONL fixture. All scratch was removed. An earlier installed-wheel fresh-process tamper check rejected a modified neutral authority file with `artifact digest mismatch for neutral_authority`; the final 116-test matrix additionally exercises fresh-process compatibility rebinding and parser-replacement fail-closed behavior.

Static checks:

- `ruff check` on the neutral core, compatibility module, and both contract test modules: passed.
- `ruff format --check` on all changed Python files: passed.
- `python -m py_compile` on all changed Python files: passed.
- `git diff --check`: passed.
- The changed worker files still expose 12 pre-existing `F821` findings (Hermes `compact_review_prompt`, `projection_capabilities`, and `Any`; Shannon `tmux_socket_for`); no new `F821` was introduced.

## Limitations

- The broad single-flight run occurred before the last internal default-capture/rebind hardening. The final affected/dependency, producer, static, fresh-process, and installed-wheel matrices were rerun afterward. The broad matrix was not repeated because its two full-dependency wheel tests had already exhausted available disk.
- No provider, cloud, runtime owner, checklist, or completion state was contacted or mutated.
- Formal T1.3 acceptance remains with the independent reviewer and release owner.
