FAIL

# T1.8 GEN-DEPLOY independent Sol review, pass 1

Reviewed exact candidate `69be00087f0d469b1e551fa8617c257f28783b7a` in `/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`. The checkout was clean and `HEAD` matched the requested commit before and after review. I treated all 7,885 changed lines as an authority/release boundary and did not trust the implementer audit or the candidate tests.

The candidate is not locally sound enough to release. Production deployment and production verification are also unavailable because no production adapter is shipped. That documented absence is a limitation, not a PASS. This report is an independent candidate review only; it does not claim formal T1.8 completion or acceptance.

## Ranked blockers

### 1. CRITICAL — `owner-installed` production authority is locally self-mintable and attacker-repinnable

`AuthorityAnchor` is unsigned caller data. It accepts caller-chosen authority, target, store, lock, root, trust digest, and executor key at `arnold_pipelines/release_authority/contracts.py:595-641`; the CLI loads it verbatim at `arnold_pipelines/release_authority/cli.py:259-262`.

The alleged external provisioning check at `arnold_pipelines/release_authority/store.py:78-119` proves only that:

- a regular SQLite file already exists;
- it is owned by the process's own effective UID and is mode `0600`; and
- four caller-computable `store_meta` strings equal the caller-supplied anchor.

There is no owner signature over the anchor/genesis, privileged installer attestation, fixed system configuration, protected parent-directory check, stable inode/device/mount identity, or unforgeable domain identity. `_initialize()` then creates the full authoritative schema at `store.py:121-224`.

Minimal probe:

```python
# Construct a local TrustBundle and owner-installed AuthorityAnchor whose paths,
# store_id, owner key, and executor key are all attacker chosen.
c = sqlite3.connect(anchor.canonical_store_path)
c.execute("CREATE TABLE store_meta(singleton INTEGER PRIMARY KEY, anchor_digest TEXT, store_id TEXT, target_id TEXT, trust_bundle_digest TEXT)")
c.execute("INSERT INTO store_meta VALUES(1,?,?,?,?)", (
    anchor.content_digest(), anchor.store_id, anchor.target_id,
    anchor.trust_bundle_digest,
))
c.commit()
os.chmod(anchor.canonical_store_path, 0o600)
DeploymentStore(anchor.canonical_store_path, anchor)
```

Observed:

```text
ACCEPTED owner-installed production:attacker-chosen .../attacker.sqlite3
TABLES 8
```

This directly falsifies review claims 1 and 2. It also collapses much of claims 3-4 because the local minter chooses both trusted owner and executor keys.

Required correction: production anchor discovery and store genesis must move behind a privileged, externally authenticated provisioning boundary that ordinary source/library/CLI callers cannot invoke or redirect. Pin an authenticated genesis to a fixed target/domain, canonical store and lock identities, protected directories, trust root, and executor/observer keys. The runtime must obtain that anchor from the trusted venue, not accept arbitrary owner-mode JSON. Add a negative end-to-end test that locally manufactures a matching `store_meta` database and proves production initialization remains impossible.

### 2. CRITICAL — a completed pre-CAS effect can be terminalized as rejected, never reconciled, and brick bootstrap

The executor durably records intent at `arnold_pipelines/release_authority/executor.py:584-586`, invokes the external effect at `executor.py:587-590`, then treats every `ReleaseAuthorityError` before `cas-selector` as safely rejected at `executor.py:593-599`. That includes an invalid/missing response after the effect happened. Terminal retry returns the stored outcome at `executor.py:538-541`; it never reconciles. `terminalize()` leaves the outstanding operation in place at `arnold_pipelines/release_authority/store.py:1356-1401`.

The failure is especially destructive during bootstrap. `begin()` has already created the target at `store.py:557-579`. A different bootstrap is then refused merely because the target row exists (`store.py:580-583`), while an ordinary deploy is refused because there is no active generation (`store.py:584-588`). Recovery accepts only unresolved indeterminate deployments (`store.py:935-946`), not this false rejection.

Probe adapter:

```python
class FenceThenLie(HermeticAdapter):
    def fence_old_writers(self, envelope):
        receipt = super().fence_old_writers(envelope)  # real effect occurs
        return receipt.model_copy(
            update={"effect_fence_digest": "sha256:" + "0" * 64}
        )
```

Observed:

```text
OUTCOME deploy-rejected fence_receipt_mismatch verify-generation
EXTERNAL_STATE True 1
SECOND_BOOTSTRAP bootstrap_epoch_closed
```

The same flaw occurs when an adapter applies `materialize-generation` and raises a typed response-loss error: the effect exists, the result is `deploy-rejected`, the outstanding operation remains, retry does not call `reconcile`, and the genesis target has fence 1 with no active generation.

This falsifies claims 2, 5, 6, and 10 and contradicts the documentation's statement at `docs/arnold/gen-deploy-release-authority.md:57-60` that ambiguous post-effect results are always indeterminate.

Required correction: after any durable intent and attempted external call, only a cryptographically/evidentially proven `NOT_APPLIED` result may become rejected. Receipt validation failures, typed transport errors, response loss, and other unproven results must reconcile or become indeterminate regardless of operation index. Do not close bootstrap genesis into a state that neither exact replay, new authority, nor signed recovery can resolve. Add effect-then-error and effect-then-invalid-receipt tests for every operation, including bootstrap.

### 3. CRITICAL — genuine CAS response-loss is indeterminate but cannot be resolved by either signed recovery strategy

After a crash at `after-effect:cas-selector`, the target selector has advanced but the store projection has not. If reconciliation returns unknown, deployment correctly becomes indeterminate. The recovery implementation cannot bridge that exact ambiguity:

- Forward-fix completion requires the adapter's resulting selector to equal the stale store selector at `arnold_pipelines/release_authority/store.py:1070-1081`, so genuine target evidence of the already-applied new selector is rejected.
- Rollback's hermetic boundary first requires the target selector to equal the binding's stale store expectation at `arnold_pipelines/release_authority/executor.py:1017-1029`, so it refuses to roll back the genuinely advanced selector.
- The store's rollback revision rule at `store.py:1083-1098` is also derived from stale store revision rather than the observed target transition.
- Recovery itself has only intent → `resolve_recovery()` → complete (`executor.py:501-524`), with no recovery reconciliation protocol after response loss.

Probe sequence:

```python
execute_deployment(..., fault_hook=crash_on_after_effect_cas_selector)
execute_deployment(..., adapter=HermeticAdapter(root, reconcile_unknown={"cas-selector"}))
# Sign recovery against store selector absent/0 and observed target selector GEN/1.
execute_recovery_resolution(..., strategy="forward-fix")
```

Observed:

```text
INDETERMINATE deploy-indeterminate cas-selector_outcome_unknown
STORE_SELECTOR absent 0
TARGET_SELECTOR {'selector_digest': 'sha256:<generation>', 'selector_revision': 1}
FORWARD_FIX forward_fix_observation_mismatch
RESOLVED_BY None
```

A fresh rollback probe failed with `stale_selector_cas` while the target remained at generation revision 1. A failed recovery attempt also leaves a recovery intent that blocks a different recovery decision at `store.py:968-977`.

This falsifies claims 5 and 6 at the central response-loss boundary.

Required correction: define and enforce explicit recovery transition tables over both durable projection and signed fresh target observation. Forward-fix must be able to adopt the already-applied exact generation/revision; rollback must be able to advance from that observed generation to the exact prior selector with a monotonic revision. Journal and reconcile recovery effects themselves, including crash/response-loss after recovery effect and before commit. Add both forward-fix and rollback tests starting from CAS-effect-applied/store-not-committed state.

### 4. CRITICAL — offline custody receipts are self-hashed, not authenticated; recomputed tampering verifies

The event chain at `arnold_pipelines/release_authority/store.py:375-459` and receipt fields at `store.py:1527-1586` use unkeyed SHA-256. The offline verifier at `arnold_pipelines/release_authority/verifier.py:167-349` accepts the event records, digest, and head from the same caller-controlled receipt. No owner/executor/custody signature authenticates the event head, terminal outcome, timestamps, event count, or bootstrap-retirement state.

Executor signatures cover operation receipt payloads in owner mode, but not event metadata or the terminal custody root. Therefore an attacker can change an uncovered field and recompute every downstream hash.

Minimal probe changed the accepted terminal event's `created_at`, set `terminal_at` to match, and recomputed `previous_hash`, `record_hash`, `event_records_digest`, and `event_head_hash` using the public canonical hash functions.

Observed:

```text
ORIGINAL_TERMINAL 2026-08-02T15:56:41.188985Z
TAMPERED_TERMINAL 2020-01-01T00:00:00Z
VERIFIED True ()
```

This falsifies claim 7's requirement that tampering any receipt field fails. Calling a value “content-addressed” or an “authenticated projection digest” (`docs/...:57-59`) does not authenticate it against malicious recomputation.

Required correction: sign a canonical custody root that covers anchor/store/domain, complete ordered event records or Merkle/hash head plus count, all decision/effect identifiers, selector/fence/writer lineage, validated/terminal timestamps, terminal outcome, and bootstrap retirement. Pin its verification key outside the receipt. Verify temporal ordering and terminal payload semantics as well as equality. Add recompute-capable tamper tests for every field, not only tests that modify a field while leaving its old digest unchanged.

### 5. HIGH — callers can fabricate “current installed” verification with an arbitrary duck-typed observer

`verify_deployment()` accepts any `ReadOnlyObservationAdapter`-shaped object at `arnold_pipelines/release_authority/verifier.py:358-365`. It trusts unsigned values from that object for selector, runtime/process birth, and old-writer status at `verifier.py:427-499`. There is no owner-installed mode gate, registered adapter provenance, challenge/nonce, observation timestamp/freshness, or observer signature.

Probe: after a valid deployment, I captured the good selector/runtime/writer values, then changed the real target to selector `absent`, revision 99, no runtime attestation, and no rejected writers. Verification through the real adapter failed. A plain object returning the stale snapshot passed:

```text
REAL False ('old_writer_rejection_disagrees', 'runtime_not_attested', 'selector_observation_mismatch')
DUCK True ()
```

This falsifies claims 4 and 8 for library verification. Signed historical effect receipts do not authenticate current live state.

Required correction: owner-installed verification must require fresh challenge-bound target observations signed by a separately pinned production observer/executor key and bound to anchor/store/target/generation/fence/selector plus observation time. Reject unregistered Protocol-shaped objects in production mode and fail explicitly with `production_observation_adapter_missing` when no production integration is installed.

### 6. HIGH — declared wheel dependency range permits canonical/signature incompatibility and raw startup tracebacks

`pyproject.toml:24` and `uv.lock:230` declare `pydantic>=2.0`, but the authority models rely on newer behavior:

- `contracts.py:16-23` imports APIs unavailable in some declared 2.0 installations;
- `StrictModel` relies on `validate_by_alias`, `validate_by_name`, and `serialize_by_alias` at `contracts.py:42-50`, whose required behavior is not available before Pydantic 2.11.

Disposable minimum-range probe with Pydantic 2.10.6:

```text
PYDANTIC 2.10.6
DUMP_SCHEMA_KEY False
DUMP_SCHEMA_ID_KEY True
ROUNDTRIP ValidationError
```

That changes canonical bytes from alias `schema` to field name `schema_id`, breaks model round-trip, and makes signatures/digests version-dependent. Under Pydantic 2.0, the installed entry point can fail during module import before `cli.main()` establishes its typed traceback-free boundary.

The installed-wheel fixture masks this by creating a venv with `system_site_packages=True` and installing the wheel `--no-deps` at `tests/installed_wheel/conftest.py:50-67`; it tests only the review environment's already-new Pydantic.

This falsifies claims 3, 9, and 10 for supported installations.

Required correction: set and lock the actual minimum compatible version (at least `pydantic>=2.11,<3`, subject to a clean minimum-version proof), build/install with declared dependencies in an isolated venv, assert module origin is inside that venv, and byte-compare canonical artifacts/signatures/schemas between source, minimum supported wheel, and locked wheel.

### 7. HIGH — the executor permit is a Python name-mangling convention, not an unforgeable capability

`_ExecutorPermit` is importable at `arnold_pipelines/release_authority/store.py:49-52`. The secret is an ordinary instance attribute created at `store.py:63`, reachable as `store._DeploymentStore__permit_secret`. The supposedly private begin methods are intentionally fetched by their mangled names at `arnold_pipelines/release_authority/executor.py:502-524` and `executor.py:536-539`; tests do the same at `tests/arnold_pipelines/release_authority/test_security_durability.py:338-357`.

A caller can construct `_ExecutorPermit(store._DeploymentStore__permit_secret, envelope_id)` or call `_DeploymentStore__begin_execution` and receive one. Production effect completion still checks an executor signature, but the fabricated permit can write intent/terminal custody and claim 4 explicitly says no caller can fabricate the permit.

Required correction: do not model a security boundary with Python privacy. Put mutation custody behind a privileged process/service boundary or make every state transition depend on independently authenticated evidence and a server-held capability that cannot be read from the caller's address space. Remove public/importable mutation primitives that can create custody events without such evidence.

### 8. HIGH — path and lock confinement is lexical and symlink/inode-race unsafe

Path normalization rejects only non-absolute spelling and literal `..` at `arnold_pipelines/release_authority/contracts.py:101-105`. Store confinement checks only `Path.parents` lexically at `store.py:538-545`. A signed path such as `/target/alias/effect` passes while `/target/alias` can be a symlink to `/outside`.

The execution lock at `store.py:271-283` creates/open-follows `canonical_lock_path` with `a+b`; it does not validate owner/mode, reject symlinks, pin inode/device, or protect against unlink-and-replace. Two processes can then lock different inodes for the same path. The store's file precheck is also separated from subsequent SQLite opens, leaving a same-UID path replacement window.

This leaves claims 1, 2, 5, and 8 unproved at filesystem boundaries even if finding 1 were fixed.

Required correction: provision store/lock/root in protected directories; open with no-follow and safe flags; verify stable inode/device/owner/mode; keep trusted descriptors; traverse effect paths descriptor-relative with `openat`-style no-follow semantics; and add symlink, hardlink, lock-unlink/replacement, and two-process race tests. A production adapter must enforce the same descriptor-rooted path domain.

## Additional high/medium completeness gaps

1. **Owner-mode adapters are arbitrary Protocol objects.** `execute_deployment()` and `execute_recovery_resolution()` reject actual `HermeticAdapter` instances for owner mode at `executor.py:430-495`, but any wrapper/duck type is treated as a production adapter. A genuine pinned executor signature is useful containment, but there is no authenticated adapter registration/domain identity, and finding 1 lets the attacker choose that executor key. Production integration is absent, not demonstrated fail-closed against masquerading library objects.

2. **`resolve --adapter production` touches the store before reporting the missing integration.** Argument evaluation constructs `DeploymentStore(..., create=False)` at `arnold_pipelines/release_authority/cli.py:467-476` before `_adapter()` supplies `None` to the executor. Store construction runs owner checks, changes WAL mode, and executes schema initialization (`store.py:121-224`). The missing production boundary must be checked before opening or mutating custody, as deploy already does at `cli.py:434-449`.

3. **Public schema and validation registries disagree.** `schemas --name` exposes twelve contracts at `cli.py:231-247`; `validate --kind` accepts only seven at `cli.py:106-122`. It cannot validate `bootstrap-decision`, `verification-report`, `target-status`, `offline-signing-request`, or `recovery-resolution-receipt`. Use one shared registry and parity-test every public contract.

4. **Installed-wheel proof is not hermetic enough.** Besides reusing system packages, it does not assert imported module origin, does not test the declared minimum dependency set, and compares parsed schema JSON rather than byte/canonical parity. The release-authority Python files present in the built wheel were byte-identical in the secondary inspection, but the present tests do not fully prove that property or dependency-semantic parity.

5. **CLI artifact writes are not crash-durable.** `_write_json()` writes directly with `Path.write_text()` at `cli.py:78-91`; there is no exclusive temporary file, file fsync, atomic rename, or parent-directory fsync. These outputs are not themselves mutation authority until signed/consumed, but the implementation does not meet the requested partial-write/fsync review standard.

## Positive implementation findings

These do not offset the blockers:

- Strict Pydantic models in the locked environment reject extras and scalar coercion, and canonical JSON is deterministic (`contracts.py:42-70`).
- Owner Ed25519 verification binds canonical decision bytes, owner identity, exact capability, target, key validity, decision issue/expiry, and signed payload digest (`signing.py:98-147`).
- Envelope construction requires exact bootstrap or ordinary decision sets; common anchor/store/generation/selector/fence binding; exact lineage; and exact operation/path/service scope (`envelope.py:54-213`).
- With a genuinely external anchor and executor key, typed operation receipts are tightly bound and executor-signature checked (`executor.py:272-405`, `signing.py:30-67`).
- SQLite uses WAL, `synchronous=FULL`, `BEGIN IMMEDIATE`, foreign keys, and a busy timeout (`store.py:121-129`), and ordinary deployment/supersession/recovery use the same nominal target lock.
- The public deploy CLI checks missing production integration before opening the store (`cli.py:434-449`). No production transport is shipped, as documented.
- Current-environment source and installed-wheel happy-path tests pass.

## Commands and results

All generated state was under pytest/macOS temporary directories or `/tmp`; no source, commit, deployment, SSH target, or cloud state was changed.

```text
git rev-parse HEAD
69be00087f0d469b1e551fa8617c257f28783b7a

git show --stat --oneline 69be00087f0d469b1e551fa8617c257f28783b7a
20 files changed, 7885 insertions(+), 1 deletion(-)

.venv/bin/python -m pytest -q tests/arnold_pipelines/release_authority
89 passed in 4.82s

.venv/bin/python -m pytest -q tests/characterization/test_import_surface.py tests/test_pipeline_run_cli.py
78 passed in 4.16s

python -m pytest -q tests/installed_wheel/test_release_authority_entrypoint.py
2 passed in 14.12s

git diff --check 69be00087f0d469b1e551fa8617c257f28783b7a^ 69be00087f0d469b1e551fa8617c257f28783b7a
PASS

.venv/bin/python -m compileall -q arnold_pipelines/release_authority
PASS

uv pip check --python .venv/bin/python
All installed packages are compatible

uv lock --check
Resolved 81 packages; PASS

git status --short
<empty>
```

The first installed-wheel invocation used `.venv/bin/python` and failed at fixture setup because that review venv has no `pip` module; it did not exercise the candidate. I repeated the same wheel test with the host Python that has pip, yielding the two passing tests above. This infrastructure retry is reported explicitly rather than hidden.

Adversarial probes and observed results are recorded under blockers 1-6. The key outputs were:

```text
owner store self-mint: ACCEPTED owner-installed; TABLES 8
pre-CAS real fence + invalid receipt: deploy-rejected; external writers_fenced=True
second genesis after rejection: bootstrap_epoch_closed
CAS response-loss forward-fix: forward_fix_observation_mismatch; resolved_by=None
recomputed offline timestamp tamper: VERIFIED True ()
drifted live target through stale duck observer: DUCK True ()
Pydantic 2.10.6 alias round-trip: schema absent, schema_id present, ValidationError
```

## Disposition

The exact candidate commit must not be accepted as T1.8 GEN-DEPLOY authority. Findings 1-6 are independent release blockers; findings 7-8 independently falsify explicit permit/path/serialization claims. Green candidate tests demonstrate only the modeled hermetic happy path and selected faults in the locked development environment.

Formal T1.8 acceptance remains a separate owner decision after corrections and a new independent review. Production availability remains false until an actual authenticated production mutation adapter and fresh observation adapter are implemented, integrated, and proven against the corrected external provisioning, crash recovery, filesystem, packaging, and receipt-authentication boundaries.
