# HARD FAIL — T1.3 independent Luna review pass 5

## Exact candidate

Reviewed clean worktree `/private/tmp/arnold-critique-recovery-contract-bundles-20260802` at:

```text
commit 4099225612f7f0b9bcc57be07c7a77c59a933234
tree   c4815fb8542bab32fd5aaee3da679dc27dc431da
parent fe1786c298361454a73754536ecf7de2f7b4bd69
```

Status was clean before and after review. The commit changes the 19 paths reported by `git diff-tree`; no candidate/Git/cloud/provider/checklist state was mutated. Prior pass-4 report SHA-256 `04fdf319...` and repair report were read but not trusted.

## Verdict

**HARD FAIL.** The alternate `arnold.pipeline.model_seam` typed-success bypass is closed, neutral ownership is materially corrected, exact byte handling is improved, and all focused tests pass. However, the claimed authenticated physical provider/session/attempt boundary remains publicly self-attested.

`ProviderTranscript.capture_transport` is a public classmethod at `arnold/pipeline/contract_bundles.py:232-275`. It accepts caller-provided bytes and caller-provided `adapter_id`, schema, runtime generation, physical provider, exact model, provider/dispatch sessions, attempt, retry ordinal, tool mode, worker/auth/capture channels. After shape checks it sets `adapter_authenticated=True` itself (`:269-274`). There is no adapter capability, signature, WBC/transport receipt, pinned adapter identity, private constructor token, or independently authenticated route record.

Consequently, any in-process caller can construct the exact object the binder treats as authenticated. The candidate's own helper `_transport_capture` at `tests/arnold_pipelines/megaplan/test_contract_bundles.py:55-84` demonstrates this public minting. Tests then successfully bind such synthetic captures (for example the hidden-followup test at `:1020-1037` reaches semantic digest comparison, proving the caller-minted capture passed transport authority).

The new contradiction test at `:958-991` proves only that caller claims must equal the caller-minted receipt. It does not authenticate which physical route/session/attempt produced that receipt. An attacker simply mints a second `capture_transport` object over the same raw bytes with the desired internally consistent route identity. This is the same trust-root defect as pass 4 moved into a richer dataclass.

This is not an arbitrary `__code__` takeover demand. It uses only the shipped public API as designed, with no monkeypatching or code mutation.

## Finite matrix

| Requirement | Verdict | Evidence |
|---|---|---|
| Exact candidate identity/cleanliness | PASS | commit/tree/parent and clean status reproduced |
| Self-attested cross-route/session/attempt closure | **FAIL** | public constructor converts caller metadata into `adapter_authenticated=True` |
| Shannon embedded identity contradiction | PASS locally | parser checks embedded session/model against supplied capture; tests pass |
| Alternate `arnold.pipeline.model_seam` typed-success bypass | PASS | mapping/JSON-only path raises `UnsupportedModelOutputAuthority`; 12-test seam suite passes |
| Neutral registry/binder/repair/preflight ownership | PASS | neutral and Megaplan objects/operations are identical in focused tests |
| Exact raw-byte preservation | PASS in covered adapters | bytes-only transport capture, invalid UTF-8 rejection, Shannon/Codex coverage pass |
| Source focused parity | PASS | exact suites below |
| Installed parity | NOT independently rebuilt in this review | implementer claim not promoted; not needed for decisive FAIL |
| New bypass scan | **FAIL** | public authenticated-capture mint is a direct new/remaining bypass |

## Commands and results

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -p no:cacheprovider -q \
  tests/arnold/pipeline/test_contract_bundles.py \
  tests/arnold/pipeline/test_model_seam_neutral.py \
  tests/arnold_pipelines/megaplan/test_contract_bundles.py
```

Result: `85 passed in 7.72s`.

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/megaplan/test_contract_bundles.py \
  -k 'authenticated_capture or hermes_physical or neutral_and_megaplan or unsupported_pipeline or binding_rejects_channel'
```

Result: `10 passed, 52 deselected in 0.25s`.

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold/pipeline/test_model_seam_neutral.py
```

Result: `12 passed in 3.99s`.

The green tests are real but encode the faulty trust assumption by constructing “authenticated” captures through the same public factory used by the counterexample.

## Required bounded correction

Make authenticated transport capture unforgeable by ordinary consumers. The physical adapter boundary must supply an owner-/capability-bound receipt covering exact raw bytes, route/model/session/attempt/retry/channel/runtime identities. The neutral binder must verify that receipt against an independently pinned adapter/transport trust root; a boolean set by a public constructor is insufficient. Keep a separate public untrusted transcript constructor if useful, but it must never satisfy production binding.

Then replay identical raw bytes under two caller-selected physical routes/sessions/attempts using only public APIs; both must fail unless backed by their own authentic adapter receipts. Retain the passing neutral ownership, model-seam fail-closure and exact-byte behavior.

## Boundary

No formal T1.3 completion is claimed. Arbitrary in-process code-object takeover remains outside scope. This HARD FAIL is based solely on ordinary public-API self-attestation. No live provider/cloud endpoint was contacted.

The report SHA-256 is recorded externally after finalization.
