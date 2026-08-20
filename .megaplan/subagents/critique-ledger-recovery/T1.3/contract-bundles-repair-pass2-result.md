# T1.3 contract-bundles repair pass 2

Verdict: FAIL — the scoped repair is committed and locally verified, but two requested invariants remain false and no formal completion is claimed.

## Commit and tree

- Worktree: /private/tmp/arnold-critique-recovery-contract-bundles-20260802
- Commit: ddb764b30cedf3774ff5ca665a85a62090607b21
- Tree: clean immediately after commit.
- Master checklist and cloud/provider/runtime state were not changed.

## Files changed

arnold_pipelines/megaplan/contract_bundles/__init__.py, all four shipped contract manifests, handlers/execute.py, handlers/finalize.py, orchestration/critique_runtime.py, model_seam.py, workers/_impl.py, agent_adapters/_oneshot.py, and tests/arnold_pipelines/megaplan/test_contract_bundles.py.

## Implemented and locally proven

- Family-prefix acceptance was removed. The immutable exact registry covers provider/model/tool tuples for current Codex, Claude/Shannon, Hermes, DeepSeek, Fireworks, Kimi, GLM, MiMo, OpenAI, xAI, and MiniMax route identities. Each manifest carries the exact route matrix; startup rejects omission, drift, or mismatch.
- Manifest/artifact bytes, bundle digest, required artifact-role set, enforcement labels, callable module/file identity, and canonical bundle object identity are rechecked at consumer use. A dataclasses.replace bundle and a swapped/rebound route registry fail closed.
- Mutable list subclasses were removed. Nested manifest values use immutable tuples and mapping proxies. The production lookup captures the canonical registry and does not use the rebindable _BUNDLES compatibility view.
- repair_once derives schema/semantic invalid pointers independently from the exact original object and raw frame; caller error text is not trusted. Exactly one independently failing pointer is required, valid subtrees and record identities are preserved, raw/object digests are checked, and repair advances object revision by one.
- Admitted payloads are frozen. Critique and finalize re-materialize only from the immutable admitted authority before harness projections. Finalize writes an execution-artifact digest into its binding receipt, and execute-entry rejects a changed or unreceipted finalize.json.
- One-shot adapter metadata now preserves auth/provider-error metadata, worker/auth channel, attempt index, capture, and contract payload fields.
- The legacy critique normalizer no longer strips producer fields before the bundle boundary; the canonical binder must reject raw/object disagreement.
- Fresh-process source and installed-wheel results match for accepted output, unknown model, wrong-provider model, and forged bundle attacks.

Final bundle digests:

    critique:prompt_only  sha256:81853ce3117c8047dd538450bc48b3095d13699d1b7894d983af1377e792a7cd
    critique:tool_enabled sha256:405eb4844d5f941352c4b67ad22d5ff753dfeb1fb775d8cd0ef149c3c53f10b6
    finalize:prompt_only sha256:85ea1b75b22fab8a8856d22987896a42c74f4c64b114239c4378c62cb10b40c6
    finalize:tool_enabled sha256:58cfddb980e5fefe62085e2629a2446f0b55a711cae687431385a8a2fe895fc4

## Adversarial probes

- Unknown gpt-not-a-real-model, family-spoofed gpt-5.6-evil, Claude model on Codex, DeepSeek typo, and GPT model on Shannon: all rejected.
- Forged dataclasses.replace bundle retaining the old digest: rejected as bundle_stale.
- Fabricated repair error for valid /checks/0/question: rejected.
- Base-container mutation, nested manifest mutation, route swap, and _BUNDLES module rebinding: cannot alter production authority.
- Installed wheel __init__.py byte append: fresh import exited 1.
- Installed manifest registry-field removal: fresh import exited 1.
- Malformed, duplicate-key, non-finite, truncated, prose-appended, wrong-frame, raw-digest, and output-digest probes remained fail closed.

## Test and static results

Focused final command:

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:cacheprovider -q tests/arnold_pipelines/megaplan/test_contract_bundles.py tests/orchestration/test_critique_custody.py tests/orchestration/test_parallel_critique.py tests/arnold_pipelines/megaplan/test_m8a_finalize_wiring.py tests/arnold_pipelines/megaplan/test_model_seam_recovery.py tests/arnold_pipelines/megaplan/test_phase_wbc_resume_lifecycle.py

Result: 87 passed.

Broader dependency closure:

    TMPDIR=/tmp/arnold-t13-pass2 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:cacheprovider -q tests/arnold_pipelines/megaplan tests/orchestration

Result: 6704 passed, 6 failed, 2 subtests passed in 450.48 seconds. The six failures are the same five disposable cloud quickstart tests that cannot infer a git origin in their temporary repositories, plus the existing wbc_boundary_discovery_rules M6 fresh-hash mismatch. No failure exercised the repaired bundle boundary.

py_compile passed for all changed Python files; git diff --check and ruff format --check passed. ruff check --select F821 still reports the three pre-existing _attach_next_step_runtime diagnostics in handlers/execute.py; no new F821 was introduced.

## Packaging proof

python -m build --wheel --no-isolation --outdir <temporary-dist> . completed successfully. The wheel was installed into a fresh venv outside the source tree with the declared project dependencies, including PyYAML, Pydantic, python-ulid, psutil, OpenAI/Anthropic clients, HTTP/runtime packages, PyJWT, discord.py, and pytest.

The installed package resolved from site-packages, loaded all four routes, and produced byte-identical conformance-vector output to the source checkout. The installed wheel contained all four manifests and both fixtures. Fresh processes rejected installed-code tampering and manifest registry-field tampering.

## Remaining failures and external owner evidence

FAIL: Hermes and Shannon still have legacy envelope parsing and construct a canonical tool-capture frame from normalized worker state before the public bundle binder. The critique normalizer is now non-lossy and the binder checks raw/object equality, but an untouched provider transcript is not yet the sole parser authority at every producer seam. Closing this requires a separate capture-plumbing change and producer fixtures for real provider transcripts.

FAIL: The shared authority remains located under the Megaplan package rather than being promoted into a neutral Arnold core module consumed by every non-Megaplan pipeline. Alternate paths were not migrated in this pass.

The runtime-instance digest now binds worker/session/channel/attempt metadata when supplied by production handlers, but no live provider, installed-owner, interpreter attestation, Hermes/Shannon/Codex capture, deployment proof, or sidecar recovery evidence was available or authorized. No cloud, provider, or runtime mutation was performed.
