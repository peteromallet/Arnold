FAIL

# T1.3 immutable contract bundles — independent Luna review pass 2

Candidate reviewed exactly: `97904d0fd8cba80c316f9607d3ac80381da77343`.

The checkout was clean at the pinned commit. I did not edit the worktree,
commit, checklist, cloud, provider, or runtime. Only this artifact was written.

## Ranked blocking findings

### 1. Unknown and wrong models are admitted by family-only matching

`ContractBundle.verify_runtime()` accepts any model whose inferred family is in
the broad manifest list at
`arnold_pipelines/megaplan/contract_bundles/__init__.py:232-246`.
All shipped manifests have `models: []` and allow every listed family. There is
no provider/model compatibility matrix.

Independent probe:

```text
python - <<'PY'
import json
from arnold_pipelines.megaplan.contract_bundles import bind_and_validate_output, canonical_json
p = json.load(open("arnold_pipelines/megaplan/contract_bundles/fixtures/critique_valid.json"))
raw = canonical_json(p)
for model in ("gpt-not-a-real-model", "codex-not-a-real-model", "claude-not-a-real-model", "deepseek-evil"):
    h = bind_and_validate_output("critique", p, raw, provider="codex", model=model,
        tool_mode="prompt_only", expected_ids=["C1"])[2]
    print(model, h.accepted, h.code.value)
PY
```

Observed: all four returned `True accepted`. Missing model is rejected, but
unknown and provider-incompatible model identities are not. This violates
invariant 5 and weakens invariant 2.

### 2. A forged bundle can retain the shipped digest while changing runtime policy

Startup validation checks manifest references only while loading at
`contract_bundles/__init__.py:353-496`. `validate_output()` calls only the label
comparison in `_verify_enforcement_identity()` at `:770-788`; it does not
revalidate the bundle digest, manifest bytes, artifact references, or callable
identity at the consumer boundary (`:912-913`). `make_binding()` trusts the
supplied `ContractBundle` fields (`:1184-1195`).

Independent `dataclasses.replace()` attack changed
`runtime_compatibility.providers` to `['evil-provider']`, retained the original
`bundle_digest`, made a binding for `evil-provider`, and passed it to
`validate_output()`. Observed: `accepted=True, outcome=NO_FINDING,
code=accepted`.

The binding does not prove that the manifest/runtime policy belongs to the
shipped bundle. This is a forged-bundle/runtime-drift failure.

### 3. The one-repair API trusts caller-supplied validation errors and changes valid fields

`repair_once()` requires one pointer and that it appear in the caller-provided
`validation_errors` map at `contract_bundles/__init__.py:1271-1308`, but it never
independently proves that the original object is invalid at that pointer. A
disposable probe started with the fully valid critique fixture, changed only
`/checks/0/question`, supplied a fabricated error for that pointer, and supplied
matching repaired raw bytes.

Observed: `repair_once()` returned the changed object with
`health.accepted=True`. A valid field can therefore be rewritten if recovery
forges the error map, violating the pointer-only invariant.

### 4. The claimed deep immutability is bypassable, and the route registry remains rebindable

`_FrozenList` is a mutable `list` subclass at
`contract_bundles/__init__.py:36-52`; `_deep_freeze()` installs it for every
manifest list at `:303-314`. Calling the base method bypasses the override:

```text
providers = get_bundle("critique").manifest["runtime_compatibility"]["providers"]
list.append(providers, "evil-provider")
```

Observed: the manifest list changed and a subsequent normal binding for
`provider="evil-provider"` was accepted while the stored bundle digest was
unchanged. `preflight_contract_bundles()` detects mutation only if called;
`get_bundle()` does not preflight (`:542-588`).

Separately, `_BUNDLES` is a reassignable module global (`:533-539`), and lookup
reads it directly (`:567-588`). Replacing the prompt-only entry with the
tool-enabled bundle made `get_bundle("critique", tool_mode="prompt_only")`
return the tool bundle. Preflight detected the rebind only afterward.

This fails invariant 4 despite the ordinary `mappingproxy` mutation tests.

### 5. The bound snapshot is not the immutable downstream authority

The production handlers create a mutable `deepcopy` snapshot at
`orchestration/critique_runtime.py:967-972` and
`handlers/finalize.py:2453-2459`, but the contract API exposes/retains ordinary
`dict` objects; `_normalize_admitted_payload()` returns a mutable dict at
`contract_bundles/__init__.py:744-767`.

Critique continues mutating `worker.payload` after binding at
`critique_runtime.py:1027-1083` and writes custody data from that projection at
`:1109-1113`. More importantly, finalize binds `worker.contract_payload`, then
passes the different mutable `worker.payload` into `_write_finalize_artifacts()`
(`finalize.py:2542-2551`). That function mutates task graph, baseline,
validation, evidence, and other fields at `finalize.py:2163-2291`, and writes
the mutated object as downstream `finalize.json` at `:2296-2305`.

There is no rebind or whole-object digest check after those mutations, and
downstream execution reads `finalize.json` (for example
`handlers/execute.py:709`). The binding sidecar's admitted payload is therefore
not the immutable object consumed as execution authority. This is the original
post-bind replacement/mutation blocker in snapshot/projection form.

### 6. A shadow legacy parser/normalizer still precedes the public bundle boundary

Real worker paths still parse/capture through `capture_step_output()` and run
`_normalize_step_payload_for_audit()` before the bundle binder:

- Codex timeout recovery: `workers/_impl.py:3758-3783`.
- Codex normal path: `workers/_impl.py:3962-3987` and `:4280-4302`.
- Hermes path: `workers/hermes.py:2538-2554`.
- Shannon path: `workers/shannon.py:3000-3040`.
- The legacy critique normalizer strips finding fields at
  `workers/_impl.py:2961-3001`.

Scratch promotion also has an independent JSON parser/schema path at
`handlers/structured_output.py:52-75` and `:136-237`. The binder later compares
digests, so many transformations fail closed, but production still has
multiple parser/normalizer authorities and the legacy path can replace the
object before binding. This violates invariant 6. Finalize additionally
imports a second model-output schema registry from `finalize_contract.py:12-201`
via `contract_bundles/__init__.py:700-731`.

### 7. Revision and runtime identity are optional/default and not actual runtime identity

`bind_and_validate_output()` defaults `object_revision=0` and
`repair_attempt=0` at `contract_bundles/__init__.py:1137-1139`; `make_binding()`
also defaults provider/model/tool and revision values at `:1170-1179`.
Production critique/finalize calls omit the revision and repair identity
(`critique_runtime.py:972-985`, `finalize.py:2457-2469`), so independent
attempts all bind as revision zero / first attempt.

The stored `runtime_digest` is only a digest of manifest compatibility fields
and `expected_runtime` (`contract_bundles/__init__.py:317-323`), not the actual
interpreter, installed wheel/code identity, worker engine, provider session, or
runtime instance. It cannot detect runtime drift that preserves the manifest.

### 8. Artifact references are not omission-resistant or bound to enforcement callables

Manifest loading iterates whatever `artifact_refs` entries exist at
`contract_bundles/__init__.py:391-406`; it never requires parser, capture,
schema, normalizer, semantic validator, route, adapter, and runtime labels to
be present or linked to `enforcement`. The `enforcement` values are merely
non-empty strings (`:460-480`), and `_verify_enforcement_identity()` compares
those strings rather than resolving and hashing the callable actually invoked.
The shipped manifests contain useful source hashes, but consumer-side checking
is not omission-resistant and the forged-bundle attack above bypasses startup
provenance entirely.

### 9. Adapter/provider-error metadata is not preserved consistently

The generic one-shot adapter projection preserves only `capture_output` and
`contract_payload` at `agent_adapters/_oneshot.py:142-149`; it drops
`auth_metadata`, including provider-error metadata that
`WorkerResult.from_agent_result()` otherwise expects at
`workers/_impl.py:751-783`. Hermes records `provider_error_code` rather than the
`provider_error` key inspected by production handlers
(`workers/hermes.py:863-864, 966` versus
`critique_runtime.py:980-983` and `finalize.py:2464-2467`). A provider failure
that reaches a valid-looking worker result through this adapter seam is not
reliably carried into the fail-closed contract check.

## Independent reproduction of the six pass-1 blockers

| Prior blocker | Pass-2 result |
|---|---|
| Raw bytes not parsed/verified in production | Narrow binder now rejects empty, malformed, duplicate-key, non-finite, truncated, appended-prose, and wrong-frame input. **Fixed at the narrow API; shadow parsing and authority replacement remain blockers.** |
| Consumer ignored `raw_output_digest` | **Fixed:** altered raw bytes returned `raw_output_digest_mismatch`. |
| Post-bind object replacement/mutation | **Still FAIL:** mutable snapshot/projection and `finalize.json` divergence are shown in finding 5; forged pointer repair is shown in finding 3. |
| Mutable route/manifest registry | Ordinary writes fail, but base-list mutation and module-global registry rebinding succeed; **FAIL**. |
| Artifact hashes did not identify enforcement code | Fresh source/wheel reference hashes and installed-wheel tamper detection pass, but callable labels/required references are not enforced; **FAIL for omission/provenance invariant**. |
| Missing model accepted | **Fixed for missing model:** `model_missing`; unknown/family-spoofed and wrong provider/model combinations still pass, finding 1. |

## Checks run

Pinned-state check:

```text
git rev-parse HEAD
# 97904d0fd8cba80c316f9607d3ac80381da77343
git status --short
# clean
```

Focused regression and relevant-path tests:

```text
TMPDIR="$REVIEW_TMP" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/megaplan/test_contract_bundles.py \
  tests/orchestration/test_critique_custody.py \
  tests/orchestration/test_parallel_critique.py \
  tests/arnold_pipelines/megaplan/test_m8a_finalize_wiring.py \
  tests/arnold_pipelines/megaplan/test_model_seam_recovery.py \
  tests/arnold_pipelines/megaplan/test_phase_wbc_resume_lifecycle.py
# 81 passed in 2.07s
```

Broader run:

```text
TMPDIR="$REVIEW_TMP" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/megaplan tests/orchestration
# 6698 passed, 6 failed, 2 subtests passed in 460.98s
```

The six failures were five cloud quickstart tests unable to infer a git origin
from their disposable repository and one stale M6 evidence hash mismatch
(`wbc_boundary_discovery_rules`); none exercised this commit's bundle boundary.

Static/diff checks:

```text
git diff --check <parent> 97904d0fd8cba80c316f9607d3ac80381da77343
# pass
python -m py_compile <all 9 modified Python files>  # redirected pycache
# pass
ruff format --check <all 9 modified Python files>
# 9 files already formatted
ruff check --select F821 <all 9 modified Python files>
# 12 legacy Hermes/Shannon F821 diagnostics, matching the repair-result limitation
```

Wheel proof in an external `git archive` checkout:

```text
python -m build --wheel --no-isolation --outdir <scratch>/dist <scratch>/src
python -m venv --system-site-packages <scratch>/venv
<scratch>/venv/bin/pip install --no-deps --no-index <scratch>/dist/*.whl
cd /tmp && <scratch>/venv/bin/python -c \
  'from arnold_pipelines.megaplan.contract_bundles import preflight_contract_bundles; print(sorted(preflight_contract_bundles()))'
# all four routes loaded; source and wheel bundle digests matched
```

Appending one byte to the installed wheel's
`contract_bundles/__init__.py` and starting a fresh process exited 1 with
`ContractBundleStartupError: ... artifact digest mismatch for capture`.
The no-dependency venv import was not treated as a product failure because
`pyyaml` is a declared core dependency; the wheel passed with the declared
dependency environment available.

Atomic sidecar inspection passed: `atomic_write_json()` delegates to the
same-directory temp-file write, file fsync, replace, and directory fsync at
`arnold/runtime/state_persistence.py:82-106`.

## Remaining integration/owner evidence

No live Hermes, Shannon, or Codex provider capture was authorized or available;
no cloud/deployment/runtime mutation was performed; and no installed production
owner attestation proves runtime/provider/session identity or sidecar recovery
behavior. Local focused passes and wheel tamper detection do not complete formal
T1.3 or authorize deployment.

Verdict: **FAIL**.
