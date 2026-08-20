# T1.3 contract-bundle repair pass 5 — implementation result

## Result

Implemented and committed the bounded pass-5 repair in the required worktree.
This is an implementation handoff, not a formal T1.3 completion claim.

- Base commit: `4099225612f7f0b9bcc57be07c7a77c59a933234`
- Commit: `2f1500aea1d03fbf13df5c796b17bd03d17bb79c`
- Tree: `0e060b37eb8bcea19d7cefa03f00842ed92b5558`
- Branch: `fix/critique-recovery-contract-bundles-20260802`
- Worktree: `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`
- Worktree status after commit: clean
- Pass-5 independent review SHA-256 verified as
  `82eb30dfff2b634ea63259e8669aac18558aa9f20f7ec11b8c491d714e7f3b75`.

## Bounded repair implemented

### Public self-attestation removed

- `ProviderTranscript.capture_transport` and `capture_sdk_event` are retained as
  public compatibility surfaces but now always reject attempts to create an
  authenticated receipt. They cannot set `adapter_authenticated=True`.
- A directly constructed transcript with the authentication boolean set also
  fails production binding unless it carries a valid neutral authority seal.
- The exact hostile counterexample is covered: identical raw bytes reminted via
  public APIs for DeepSeek/session-A/attempt-0/critique and
  Zhipu/session-B/attempt-99/finalize both fail before binding.

### Pinned adapter-owner receipts

- Provider receipt issuance is now private to the four production adapter
  owners: Hermes, Shannon, native Shannon stream, and Codex.
- The neutral issuer verifies the immediate owner module's on-disk source bytes
  against the adapter digest pinned in every validated bundle manifest.
  All four manifests must agree on each owner trust root.
- The receipt seal covers the exact raw digest plus adapter/schema identity,
  runtime generation, frame kind, physical provider, exact model, provider and
  dispatch sessions, attempt, hidden retry ordinal, tool mode, exact contract
  route, worker/auth/capture channels, owner module, owner source digest, and
  trust-root identity.
- The seal is HMAC-authenticated with a process-private neutral authority key.
  Metadata, raw-byte, digest, owner, source-root, route, or seal mutation is
  rejected at the neutral binder/parser boundary.
- The adapter calls remain at the pass-4 exact custody points: canonical Hermes
  SDK event immediately after provider return, exact Shannon/native-stream
  stdout bytes, and exact Codex output-file/CLI bytes.

### Consumer and artifact closure

- `CONTRACT_AUTHORITY.bind_output` verifies the seal before deriving any route,
  model, session, attempt, channel, or runtime identity.
- `parse_output` independently verifies the same receipt and checks that its
  exact `contract_route` matches the selected canonical bundle.
- The four bundle manifests were refreshed with the final neutral authority,
  policy, and adapter source hashes and new bundle digests.
- Neutral authority ownership, Shannon embedded-identity contradiction, exact
  invalid-byte preservation, hidden-follow-up protection, model-seam
  fail-closure, and source/wheel parity remain covered.

## Files in commit

- `arnold/pipeline/contract_bundles.py`
- `arnold_pipelines/megaplan/contract_bundles/__init__.py`
- four pinned `arnold_pipelines/megaplan/contract_bundles/*_v1.json` manifests
- `arnold_pipelines/megaplan/workers/_impl.py`
- `arnold_pipelines/megaplan/workers/hermes.py`
- `arnold_pipelines/megaplan/workers/shannon.py`
- `arnold_pipelines/megaplan/workers/shannon_stream.py`
- `tests/arnold/pipeline/test_contract_bundles.py`
- `tests/arnold_pipelines/megaplan/test_contract_bundles.py`

## Validation

Exact pass-5 reviewer source suite, with the new public-remint and forged-boolean
regressions:

```text
87 passed in 5.40s
```

Final focused/dependency matrix from the final source bytes:

```text
139 passed in 6.07s
```

Final producer/adapter matrix from the final source bytes:

```text
48 passed in 0.26s
```

Expanded model-seam, outbound-inventory, AgentStep, and M8 regression matrix:

```text
80 passed in 8.90s
```

All four final source manifests passed content-addressed preflight.

A wheel was built from the final source, installed with `--no-deps` into a fresh
`--system-site-packages` virtualenv, and exercised from `/tmp` outside the
checkout. It proved exact neutral/Megaplan authority and registry identity,
binder/repair/preflight operation identity, four-bundle installed preflight,
public cross-route remint rejection, and mapping-only model-seam fail-closure:

```text
fresh-installed-wheel: sealed authority, registry, remint, seams ok
```

The disposable wheel/venv directory was moved to Trash after validation.

Static evidence:

- `ruff check` passed on the neutral authority, Megaplan authority policy, and
  both contract-bundle test modules.
- `ruff format --check` passed on all changed Python files.
- `python -m py_compile` passed on all changed production Python files.
- `git diff --check` passed.
- A full worker-file lint still reports pre-existing unrelated findings in those
  large files; the two new unused imports it exposed were removed before the
  final manifest hashes and test reruns.

## Boundaries and limitations

- No full 6,700+ broad matrix was rerun in this bounded pass.
- The authority seal is process-local; provider capture and critique/finalize
  consumption are intentionally an in-process custody path.
- Deliberate private-internal access, module-global mutation, arbitrary code
  execution, or code-object takeover remains outside this ordinary public-API
  correction and the stated T1.3 boundary.
- No live provider/cloud endpoint was contacted. No provider, cloud,
  production-owner, release-owner, checklist, or formal-completion state was
  mutated.
- A new independent review and the normal integration/production dispositions
  remain required before any formal T1.3 completion claim.
