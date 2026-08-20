FAIL

# T1.3 contract-bundles review pass 1

Candidate reviewed: `e0b91992b2d2e01f7d7d87ba5053394a972984c6`

Worktree was clean and at the exact requested commit. No source, commit, cloud,
deployment, or SSH state was changed. The earlier ENOSPC interruption was not
reproduced and is not counted as a code failure.

## Blocking findings

### 1. The production boundary never parses or verifies the raw transport

`bind_and_validate_output()` creates a binding directly from the already
materialized `payload` and the arbitrary `raw_output` at
`arnold_pipelines/megaplan/contract_bundles/__init__.py:641-674`. It never calls
`parse_output()` (`:420-460`), never requires non-empty raw output, and never
checks that parsed raw content equals the promoted payload.

The production calls are at
`arnold_pipelines/megaplan/orchestration/critique_runtime.py:877-890` and
`arnold_pipelines/megaplan/handlers/finalize.py:2278-2291`. Both pass the
post-promotion payload and `worker.raw_output or ""` straight to the binder.
Scratch promotion itself uses permissive `json.loads()` at
`arnold_pipelines/megaplan/handlers/structured_output.py:54-63`, so duplicate
keys and the required exact framing are already lost before the bundle parser
could see them.

Minimal reproduction, run in one disposable Python process:

```text
critique bind raw='' accepted= True outcome= NO_FINDING code= accepted
critique bind raw='not json' accepted= True outcome= NO_FINDING code= accepted
critique bind raw='{"checks":[{"id":"C1","findings":[{"detail":"clear","flagged":false}]}]} trailing' accepted= True outcome= NO_FINDING code= accepted
critique bind tool framing missing accepted= True outcome= NO_FINDING code= accepted
finalize bind missing raw accepted= True outcome= FINDING code= accepted
```

The standalone `parse_output()` correctly rejects duplicate keys, truncation,
NaN, and prose, but that helper-only behavior does not protect either shipped
production path. This directly violates requirements 1, 3, 4, 5, and 7: a
provider/tool capture failure can be accepted as semantic `NO_FINDING` when the
payload happens to be valid.

Required correction: make the production seam accept raw bytes as the source of
truth; require the selected bundle's `parse_output()` to succeed; require
non-empty raw output and exact framing/tool mode; compare the parsed payload
digest with the promoted payload digest; and reject any provider failure or
missing capture before binding/semantic acceptance. The binding must carry and
the consumer must compare the exact raw-output digest.

### 2. The consumer ignores `raw_output_digest`

At `arnold_pipelines/megaplan/contract_bundles/__init__.py:584-610`, the
consumer computes `raw_digest` but the binding comparison only checks `step`,
`bundle_id`, `bundle_digest`, `output_digest`, and `repair_attempt`. The
binding's `raw_output_digest` is never compared with the supplied raw output.

Minimal reproduction:

```text
binding_raw_digest= sha256:d7d38163...
consumer_raw_digest= sha256:2b9577f7...
accepted= True code= accepted
```

Required correction: reject missing raw bytes and require
`supplied_binding.raw_output_digest == digest_bytes(raw_output)` after strict
parsing, with the parsed payload digest also matching the binding.

### 3. Finalize and critique mutate/replace the object after the only binding

Finalize binds and records health at
`arnold_pipelines/megaplan/handlers/finalize.py:2278-2323`, then calls
`_validate_finalize_payload()` at `:2352` and
`_write_finalize_artifacts()` at `:2361`. `_write_finalize_artifacts()` mutates
the accepted model object extensively at
`arnold_pipelines/megaplan/handlers/finalize.py:2029-2059` and later lines,
including normalization, task insertion, coverage, validation jobs, baseline
metadata, and evidence fields. The written `finalize.json` therefore need not
have the `output_digest` in `finalize_contract_binding.json`.

Critique has the same shape: it binds at
`arnold_pipelines/megaplan/orchestration/critique_runtime.py:877-924`, then
legacy audit recovery can replace/rebuild the worker at `:926-968`; recovery
normalization and projection are implemented at `:1118-1197`. The rebuilt
worker drops the contract fields in `_rebuild_recovered_critique_worker()` at
`:180-198`, and the changed payload continues through custody and finalization
without a second bundle validation.

Required correction: define the exact immutable admitted object, perform all
permitted harness transformations before binding, and bind the exact object
that is persisted/consumed. Remove legacy post-bind replacement, or re-enter a
single tightly-scoped repair path that verifies the original binding, pointer
allowlist, whole-object digest, raw digest, bundle, and runtime again before any
consumer uses the result.

### 4. Bundle lookup and manifests are mutable in-process

`_BUNDLES` is a plain mutable dict at
`arnold_pipelines/megaplan/contract_bundles/__init__.py:344-368`, and
`ContractBundle.manifest` retains a mutable nested dict. `get_bundle()` reads
the mutable registry at `:386-403`; `preflight_contract_bundles()` only reads a
fresh temporary map and does not repair or replace `_BUNDLES` at `:371-383`.

Minimal reproduction:

```text
lookup_after_mutating_registry= megaplan.critique.v1.tool_enabled
preflight_routes= ['critique:prompt_only', 'critique:tool_enabled', 'finalize:prompt_only', 'finalize:tool_enabled']
lookup_still= megaplan.critique.v1.tool_enabled
manifest_tool_mode_after_mutation= tool_enabled
stored_digest_unchanged= sha256:c2077bac...
```

Thus a caller can route the prompt-only key to a different bundle or mutate
transport/runtime policy without changing the stored digest. This violates the
no-mutable-lookup and immutability requirements even though fresh import and
file tamper checks pass.

Required correction: load into a deeply immutable structure (including nested
manifest mappings), expose no mutable registry, resolve only from an immutable
route-to-bundle table, and make preflight verify the same immutable table or
fail rather than leaving a mutated table active. Also verify that each route key
matches the bundle's own `step` and `transport.tool_mode`.

### 5. Manifest artifact hashes do not identify the actual enforcement code

The bundle manifests name hashes for `model_seam.py`, `robustness.py` or
`handlers/finalize.py`, and the prompt/schema files, but the actual bundle
consumer uses different code in the new module: `_strict_output_schema()` at
`arnold_pipelines/megaplan/contract_bundles/__init__.py:463-489` and
`_semantic_errors()` at `:500-555`. The production normalizers include
`promote_scratch()` and finalize's `normalize_contract_payload()` / task graph
mutations, which are not the manifest's `normalizer` artifact. The manifest
fields are checked for presence/digest, but their ABI values are not used to
select or verify the callable that actually runs.

Required correction: bind exact parser, capture, schema, normalizer, semantic
validator, prompt, provider/model/tool, fixture, and expected-runtime
implementations to explicit code/source identities; invoke those identities at
the producer and consumer seam; and fail startup/runtime if the selected code
does not match the bundle. A declarative ABI string plus an unrelated source
file hash is insufficient.

### 6. Missing model identity is accepted

`ContractBundle.verify_runtime()` only applies model checks when `model is not
None` at `arnold_pipelines/megaplan/contract_bundles/__init__.py:181-187`.
`model=None` therefore passes runtime compatibility. The focused probe returned
`accepted=True, outcome=NO_FINDING, code=accepted` for a valid critique payload
with `provider='codex', model=None`. This leaves the actual model assumption
unbound and violates the runtime-binding requirement.

Required correction: require a non-empty actual model identity and match it to
the bundle's exact model/family policy; treat absent, unknown, or provider-error
metadata as typed contract failure.

## Checks that passed but do not clear the blockers

- Focused contract/orchestration pytest, one invocation with a dedicated temp
  root and cache disabled:

  `TMPDIR="$REVIEW_TMP" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:cacheprovider -q tests/arnold_pipelines/megaplan/test_contract_bundles.py tests/orchestration/test_critique_custody.py tests/orchestration/test_parallel_critique.py tests/arnold_pipelines/megaplan/test_m8a_finalize_wiring.py tests/arnold_pipelines/megaplan/test_model_seam_recovery.py tests/arnold_pipelines/megaplan/test_phase_wbc_resume_lifecycle.py`

  Result: `74 passed in 2.85s`.

- Source preflight and parser unit behavior passed. The targeted tests prove
  fresh digest stability, file-artifact tamper rejection, parser rejection of
  duplicate/non-finite/truncated/prose input, and the nominal repair guards.

- Wheel proof in a disposable build directory:

  `TMPDIR="$REVIEW_TMP" python -m build --wheel --no-isolation --outdir "$REVIEW_TMP/dist" .`

  Result: wheel built successfully. A fresh venv installed it with
  `pip install --no-deps --no-index`; all four manifests and both fixtures were
  present, fresh-process `bundle_help()`/`preflight_contract_bundles()` loaded,
  and all four source/wheel digests matched.

- Installed-wheel tamper probe modified only the disposable installed
  `contract_bundles/__init__.py`. A fresh process failed at import with
  `ContractBundleStartupError: ... artifact digest mismatch for parser`.

## Verdict boundary

This is a local candidate review. It does not prove formal T1.3, and it does
not authorize deployment.
