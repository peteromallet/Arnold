# T1.3 contract-bundle repair pass 4 — implementation result

## Result

Implemented and committed the bounded pass-4 repair in the required worktree.
This is an implementation handoff, not a formal T1.3 completion claim.

- Base commit: `fe1786c298361454a73754536ecf7de2f7b4bd69`
- Commit: `4099225612f7f0b9bcc57be07c7a77c59a933234`
- Tree: `c4815fb8542bab32fd5aaee3da679dc27dc431da`
- Branch: `fix/critique-recovery-contract-bundles-20260802`
- Worktree: `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`
- Worktree status after commit: clean
- Pass-4 independent review SHA-256 verified as
  `04fdf319699a28bdef634920a26237d7a6a51b5e8fa55f590d674dee904ab144`.

## Bounded repair implemented

### A. Authenticated transport capture

- Added a frozen, bytes-only adapter transport receipt in neutral Arnold core.
  It binds adapter/schema identity, runtime generation, frame kind, physical
  provider, exact model, provider and dispatch sessions, configured attempt,
  hidden retry ordinal, tool mode, worker/auth/capture channels, raw digest and
  exact raw/canonical SDK-event bytes.
- Hermes now captures the canonical SDK result immediately after
  `run_conversation`, before parsing, file fallback, summary/follow-up recovery,
  or mutable worker projection. DeepSeek, Zhipu, Fireworks and OpenRouter remain
  distinct physical routes. A later follow-up/substitution cannot replace the
  captured result.
- Shannon and native Shannon-stream retain exact stdout/transcript bytes rather
  than re-encoding decoded output. Shannon embedded model/session identity is
  checked against the receipt. Codex retains exact output-file/CLI bytes; invalid
  UTF-8 is preserved and rejected rather than normalized with replacement.
- Configured fallback attempt and hidden provider retry ordinals are captured at
  the adapter boundary. `WorkerResult` and the one-shot projection carry the
  immutable object beside legacy evidence only.
- Critique/finalize now require and parse `worker.provider_capture`; they never
  reconstruct provenance from mutable `WorkerResult` route/session/attempt
  fields. Evidence files receive the receipt's exact bytes.

### B. Neutral authority and alternate seams

- Neutral core now owns the single installed authority, canonical registry
  object, binder dispatch, repair dispatch, preflight dispatch and parser.
  Megaplan installs policy once and re-exports the exact neutral authority and
  registry objects; source and installed-wheel identity checks cover all four
  operations.
- `CONTRACT_AUTHORITY.bind_output` requires an authenticated receipt and derives
  route/model/tool/runtime identity from it. Contradictory caller claims fail
  closed.
- The real neutral `arnold.pipeline.model_seam.capture_step_output` raises the
  typed `UnsupportedModelOutputAuthority` for mapping/JSON-only model output.
  The product-local Megaplan `AgentStep` also rejects that unsupported path
  before its legacy normalizer can mint typed authority.
- The M8 outbound inventory now records the contract-bundle schema and bounded
  repair validators. Native Shannon stream is pinned in every bundle artifact
  inventory.
- No bespoke `__code__`/arbitrary in-process takeover defenses were added.

## Files in commit

- `arnold/pipeline/contract_bundles.py`
- `arnold/pipeline/model_seam.py`
- `arnold_pipelines/megaplan/agent_adapters/_oneshot.py`
- `arnold_pipelines/megaplan/contract_bundles/__init__.py`
- four pinned `arnold_pipelines/megaplan/contract_bundles/*_v1.json` manifests
- `arnold_pipelines/megaplan/handlers/finalize.py`
- `arnold_pipelines/megaplan/orchestration/critique_runtime.py`
- `arnold_pipelines/megaplan/steps/agent.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- `arnold_pipelines/megaplan/workers/hermes.py`
- `arnold_pipelines/megaplan/workers/shannon.py`
- `arnold_pipelines/megaplan/workers/shannon_stream.py`
- `docs/m8-outbound-coverage.md`
- `tests/arnold/pipeline/test_contract_bundles.py`
- `tests/arnold/pipeline/test_model_seam_neutral.py`
- `tests/arnold_pipelines/megaplan/test_contract_bundles.py`

## Validation

Focused/dependency matrix, retaining the original 116 and adding pass-4
regressions:

```text
137 passed in 6.09s
```

Producer/adapter matrix:

```text
48 passed in 0.28s
```

Model-seam, outbound-inventory and regression matrix:

```text
70 passed in 8.33s
```

The added cases cover:

- immutable same-receipt route/session/attempt/channel contradiction;
- Shannon embedded Sonnet/session-A versus claimed Opus/session-B;
- DeepSeek, Zhipu, Fireworks and OpenRouter physical Hermes routes;
- hidden follow-up substitution and retry ordinals;
- invalid byte preservation and canonical structured-SDK capture;
- mapping/JSON-only neutral model seam and AgentStep fail-closure;
- neutral/Megaplan authority, registry, binder, repair and preflight identity.

Final source preflight passed all four pinned bundles. A final wheel was built,
installed with `--no-deps` into a fresh `--system-site-packages` virtualenv, and
proved exact neutral/Megaplan authority and registry identity, binder/repair/
preflight operation identity, four-bundle preflight, and installed mapping-only
model-seam fail-closure:

```text
fresh-installed-wheel: authority, registry, seams ok
```

Static evidence:

- `ruff check` passed on the new neutral/authority/AgentStep/test surfaces.
- `ruff format --check` passed on all changed Python files.
- `python -m py_compile` passed on all changed production Python files.
- `git diff --check` passed.
- The worker files retain the same 12 pre-existing `F821` findings documented
  by pass 3; none is introduced by this repair.

## Limitations and production prerequisites

- The full 6,700+ test broad matrix was not rerun in this bounded pass. The
  original focused, producer, M8/outbound, source preflight and fresh-installed
  wheel matrices were rerun after the final source bytes.
- Provider SDKs that expose structured objects are attested as canonical SDK
  event bytes with explicit adapter/schema identity, not mislabeled as wire/HTTP
  bytes.
- Legacy transcript/text fields remain compatibility/evidence projections, but
  production authority and exact critique/finalize consumers reject their use
  without the authenticated receipt.
- Arbitrary in-process code-object takeover remains explicitly outside T1.3 and
  belongs to the T1.8/T1.9 fenced-generation/process boundary.
- No live provider/cloud endpoint was contacted. No provider, cloud, production
  owner, release owner, checklist or formal completion state was mutated.
- A new independent Luna review, integration-owner disposition, and production
  rollout evidence are still required before any formal T1.3 completion claim.
