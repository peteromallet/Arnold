# PASS — T1.3 independent Luna review pass 6

## Exact candidate

Reviewed read-only in clean worktree:

```text
/private/tmp/arnold-critique-recovery-contract-bundles-20260802
commit 2f1500aea1d03fbf13df5c796b17bd03d17bb79c
tree   0e060b37eb8bcea19d7cefa03f00842ed92b5558
parent 4099225612f7f0b9bcc57be07c7a77c59a933234
```

`git status --porcelain=v1` was empty before and after review. The recovery ancestor `6787d6363e8fc0603092913ae877db14f3b9fff8` is an ancestor. The exact ancestry path is:

```text
e0b91992b2 Bind critique and finalize outputs to immutable contract bundles
97904d0fd8 Repair T1.3 contract bundle boundaries
ddb764b30c Repair T1.3 contract bundle boundaries pass 2
fe1786c298 Harden T1.3 provider transcript authority
4099225612 Bind contract authority to adapter receipts
2f1500aea1 Seal provider receipts to pinned adapter owners
```

The candidate changes 12 paths (`361 insertions, 142 deletions`) and `git diff --check HEAD^ HEAD` passes. I read the pass-5 HARD FAIL and repair result, inspected the full candidate diff and production consumers, and reproduced the prior exploit independently rather than relying on the implementer's tests.

## Verdict

**PASS for the finite T1.3 acceptance boundary.** The pass-5 ordinary public-API self-attestation defect is closed. A caller can no longer turn chosen raw bytes plus chosen provider/model/session/attempt/retry/channel/runtime fields into an authenticated receipt through `ProviderTranscript.capture_transport`, `capture_sdk_event`, the Megaplan compatibility import, the neutral import, a direct dataclass construction, or the alternate model-seam route.

The authenticated receipt path is now separate from the public untrusted transcript path:

- `arnold/pipeline/contract_bundles.py:240-260` makes both public authenticated-capture factories deterministic rejection surfaces.
- `:490-562` issues a receipt only at the private adapter seam after matching the immediate owner module and its on-disk source digest to the immutable installed trust-root map. The HMAC covers exact raw digest plus adapter/schema, runtime generation, frame kind, physical provider, exact model, provider/dispatch sessions, attempt, retry, tool mode, contract route, worker/auth/capture channels, owner module/source digest, and trust-root ID.
- `:587-614` independently rehashes raw bytes, rechecks the installed owner root and trust-root identity, and verifies the process-private seal. Setting `adapter_authenticated=True` does not satisfy it.
- `arnold_pipelines/megaplan/contract_bundles/__init__.py:554-582` derives the only four production issuer owners from source digests present and equal in every canonical bundle manifest: Hermes, Shannon, native Shannon stream, and Codex `_impl`.
- Both parsing (`:713-760`) and the captured neutral authority binder (`:1784-1874`) verify the seal and route before deriving identity or semantic authority. Critique and finalize production consumers call this frozen authority; no production caller invokes `parse_output` directly.
- Exact capture occurs at the owner boundary: Hermes seals the canonical SDK event immediately after `run_conversation` (`workers/hermes.py:2463-2505`); Shannon seals selected transcript/stdout bytes (`workers/shannon.py:3136-3157`); native Shannon seals exact `stdout_bytes` (`workers/shannon_stream.py:1323-1343`); Codex seals exact output-file bytes or, on read failure, the exact stdout/stderr byte concatenation (`workers/_impl.py:4144-4170`). Route/session/attempt/retry/channel metadata is sealed in the same receipt and contradiction checks remain fail closed.

Static production scan found `_capture_adapter_transport` / `_capture_adapter_sdk_event` only in the neutral issuer and those four pinned owners. They are underscore-private and absent from `__all__`; the ordinary public factories remain reject-only. Deliberate private-global access, module mutation, arbitrary code execution, and code-object takeover are outside the frozen finite boundary, as they were in the repair handoff; no such mechanism is needed for or used by this PASS.

## Pass-5 counterexample replay

In a fresh source process I used identical critique bytes and attempted to mint:

1. DeepSeek / `deepseek-v4-pro` / `session-A` / attempt 0 / retry 0 / critique; and
2. Zhipu / `glm-5.2` / `session-B` / attempt 99 / retry 7 / finalize.

Both `ProviderTranscript.capture_transport` calls rejected with `NeutralContractError`; public `capture_sdk_event` also rejected. `ProviderTranscript.capture` produced only an untrusted transcript and the canonical binder refused it. A directly constructed transcript with correct raw digest and `adapter_authenticated=True` but no neutral seal was refused. The neutral and Megaplan `ProviderTranscript` and `CONTRACT_AUTHORITY` objects were identical.

The same hostile probe passed from:

- the source checkout;
- a fresh editable installation made from a `git archive` copy; and
- a fresh wheel built from the exact commit, installed with `--no-deps` into a fresh `--system-site-packages` virtualenv, and executed from `/tmp` outside the checkout.

The installed imports resolved exclusively under `/tmp/t13-pass6-wheel.7diKz7/venv/lib/python3.11/site-packages/`; editable imports resolved exclusively under the archived temporary source. Installed and editable canonical preflight exposed exactly the four critique/finalize × prompt/tool routes.

## Finite matrix

| Requirement | Verdict | Independent evidence |
| --- | --- | --- |
| Exact commit/tree/parent/cleanliness | PASS | reproduced hashes, ancestry, empty status before/after, diff check clean |
| Prior public `capture_transport` self-attestation | PASS | exact cross-route/session/attempt/retry replay rejected in source, editable, wheel |
| Public SDK-event self-attestation | PASS | public `capture_sdk_event` rejects |
| Direct boolean/dataclass forgery | PASS | missing neutral authority seal rejected before binding |
| Pinned adapter-only issuance | PASS | four owner modules only; every manifest pins the same observed source digest for each; issuer rereads owner source at issue time |
| Receipt integrity and exact route identity | PASS | HMAC covers raw digest and complete identity; binder/parser verify seal and contract route before authority |
| Physical metadata contradiction | PASS | focused tests reject model, dispatch session, attempt, auth channel and contract-route drift |
| Exact adapter-captured bytes | PASS | direct bytes on Shannon/native/Codex; declared canonical `sdk_event_json` bytes on Hermes; invalid UTF-8 and hidden-follow-up tests pass |
| Neutral ownership | PASS | neutral source contains no `arnold_pipelines`; neutral/Megaplan types, registry and executable authority are identical |
| Alternate `arnold.pipeline.model_seam` route | PASS | mapping/JSON-only typed success remains unsupported; 12-test neutral seam portion passed within the 87-test suite |
| Source/editable/installed parity | PASS | independent hostile probes and four-bundle preflight pass in all three import modes |
| New ordinary/direct/import alias bypass | PASS | static scan plus hostile imports found no authority-producing public alias |

Manifest source-root verification independently recomputed these exact values from candidate bytes and matched every canonical manifest:

```text
Hermes         sha256:a92932eef296d7e0cd7e2798a820dce6163d4d94a3cdb9904985efacf60f4fa8
Shannon        sha256:9031cc808625e2eeb6fc8157df9967f8f77ca4786035dc11293b3b5793f0c639
Shannon stream sha256:f100f262e75f305816acb14bea0108bafef199023121a868094258903571c8dc
Codex _impl    sha256:016545ace6a4d24dfc139bf3e770657931489342fcc674e358809597c00251da
```

## Commands and results

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -p no:cacheprovider -q \
  tests/arnold/pipeline/test_contract_bundles.py \
  tests/arnold/pipeline/test_model_seam_neutral.py \
  tests/arnold_pipelines/megaplan/test_contract_bundles.py
```

Result: `87 passed in 6.83s`.

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/megaplan/test_contract_bundles.py \
  -k 'public_caller or authenticated_boolean or authenticated_capture or hermes_physical or hidden_followup or neutral_and_megaplan or unsupported_pipeline or binding_rejects_channel'
```

Result: `13 passed, 51 deselected in 0.09s`.

Independent one-shot probes reported:

```text
source-hostile-public-aliases: PASS
manifest-adapter-source-roots: PASS
fresh-editable-public-aliases-and-preflight: PASS
fresh-installed-wheel-public-aliases: PASS
```

`git merge-base --is-ancestor`, `git diff --check`, and `git fsck --no-dangling --no-progress` also passed. The worktree remained clean.

## Boundary

This is a finite acceptance of commit `2f1500aea1d...` for the stated T1.3 contract-bundle boundary, not a production deployment or whole-repository claim. I did not run a live provider, the full repository suite, or exercise private-global/code-execution compromise. T1.2/T1.6/T1.8 still own attempt/effect custody, route admission, and installed-generation deployment; this PASS does not complete those tasks.

No source, Git, cloud, provider, owner, checklist, or formal completion state was mutated. Only this review report was written. Its SHA-256 is recorded in the parent handoff.
