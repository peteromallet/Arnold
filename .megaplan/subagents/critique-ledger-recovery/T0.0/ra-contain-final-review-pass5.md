# T0.0 RA-CONTAIN independent release review — pass 5

Verdict: **FAIL** for local release candidacy.

Reviewed read-only at exact commit `a0334cfbc9e3bfde6aa3310c45975d539153b1f5` (`HEAD` matched exactly). No repository, cloud, deployment, provision, commit, or push state was changed. This report is the only written artifact.

## Release blockers

### 1. The default owner head does not prevent a valid-prefix rollback

The new head detects journal-only rollback and head-only rollback, but the default head is `journal.head` beside the journal (`containment.py:316-325`). The real CLI constructs `ContainmentStore(args.journal, capability)` and has no owner-anchor-path option (`containment.py:947-979`). Thus both files are in the same local rollback/failure domain.

Independent reproduction:

```python
r = s.issue(exact_tuple=SCOPE, expected_cursor=0,
            expected_revision="0" * 64, issuer="owner", reason="x")
old_journal = journal.read_bytes()
old_head = head.read_bytes()
st = s.status()
s.terminate(decision_id=r["decision_id"], expected_cursor=st["cursor"],
            expected_revision=st["journal_digest"], issuer="owner", reason="done")
journal.write_bytes(old_journal)
head.write_bytes(old_head)
assert ContainmentStore(journal, CAP).status()["receipt"]["state"] == "active"
assert ContainmentStore(journal, CAP).check(SCOPE, "observe").decision == "ALLOWED"
```

Observed: `both_rollback committed 1 active ALLOWED`.

Journal-only and head-only rollback do refuse with `AuthorityMismatch`; a rollback of both to a previously valid authenticated pair is accepted. A genuinely off-volume, owner-protected Release Authority anchor could make that latter rollback impossible as an operational assumption, but this commit does not enforce that assumption. Its constructor merely permits an alternate path, while the real CLI silently selects the adjacent path. An adjacent head must not be described as external rollback protection.

Required fix: make the production path require an accepted Release Authority-provisioned, independently protected anchor/capability domain; remove the same-directory default from production wiring and fail if no distinct owner anchor is supplied. Add a real-CLI test proving the journal and head cannot silently share the incident volume.

### 2. Pending-head persistence can destroy the last committed anchor

`_write_anchor_direct()` opens the existing head with `"wb"` (`containment.py:478-488`) before the pending intent is durable. A write failure after truncation leaves a partial head. The caller raises `StorageError`, but the old committed anchor is gone and `recover()` cannot read an exact pending/base state.

Independent reproduction injected a write that wrote eight bytes and then raised:

```text
pending_partial_issue StorageError owner head write/fsync is uncertain
pending_partial_head_bytes 8 old_len 512
pending_partial_status CorruptAnchor owner head is invalid
pending_partial_recover CorruptAnchor owner head is invalid
```

This directly fails the required pending-head mkdir/open/write/flush/fsync/close crash analysis: a crash or failure while writing pending intent can irrecoverably destroy the last committed anchor. The repository tests cover several `fsync` counts, but not this destructive partial-write/close window.

Required fix: never overwrite the committed head in place. Persist pending intent through a separately named, atomically written and authenticated record (or a two-slot protocol) so every failure before replacement preserves the committed anchor, and every post-replacement ambiguity remains visibly pending and fail-closed. Test partial write, flush, fsync, close, replacement, directory fsync, and fresh-process recovery separately.

### 3. A final persistence ambiguity can become ordinary idempotent success

`_begin_and_commit()` catches final head-write ambiguity and calls `_best_effort_pending()` (`containment.py:676-695`). That backstop silently swallows all write errors (`containment.py:510-523`). If the atomic replace already succeeded but parent-directory fsync is ambiguous, and the backstop fails, the committed new head remains readable. A retry then follows the ordinary active duplicate path in `issue()` and returns success.

Independent reproduction failed the final parent-directory fsync and made the best-effort pending write fail:

```text
first StorageError final parent fsync uncertainty
fsync_calls 3 head {"anchor_mac":"..."
retry ambiguous committed
```

This violates the explicit rule that post-append ambiguity can never become ordinary idempotent success. Normal pending-intent failures do refuse, but the required property must hold for the failure of the ambiguity backstop itself.

Required fix: represent final commit as an unambiguous authenticated state transition, or force every uncertain path to a durable indeterminate marker that `status`, `check`, issue, terminate, and retry refuse. Do not swallow failure of the backstop; add a fresh-process regression where replace succeeds, directory fsync/close fails, and pending persistence also fails.

### 4. Reconcile itself can tear the journal and make exact recovery impossible

`reconcile()` appends its audit record directly to the journal (`containment.py:863-876`). A partial append leaves a torn journal; the next fresh process fails `_replay()` with `CorruptJournal`, so it cannot append the required reconcile transition or adopt/abort the exact pending candidate/base.

Independent reproduction left an exact pending issue, then wrote half of the reconcile record and raised:

```text
reconcile_partial_call StorageError reconcile append ambiguity
reconcile_partial_status CorruptJournal invalid or torn journal
reconcile_partial_retry CorruptJournal invalid or torn journal
```

Required fix: give reconcile its own durable write-ahead/atomic record protocol, or make a torn reconcile append recoverable from authenticated pending intent without guessing. Test failures during reconcile mkdir/open/write/flush/fsync/close, journal directory fsync, final head replace, and final head directory close in a fresh process.

### 5. Owner capability authentication is not an enforceable production boundary

The API still authenticates mutations primarily by comparing caller-provided `issuer` to `owner_id` (`containment.py:336-339`). The optional capability check is broken by the dataclass definition: `secret` has `compare=False` (`containment.py:119-123`). Therefore capabilities with the same owner ID but different secrets compare equal.

Independent reproduction:

```text
equality_different_secret= True
wrong_same_owner_capability active
```

The secret also has multiple leak/extraction surfaces:

- `OwnerCapability.secret` is a public dataclass attribute (`cap.__dict__` contains the raw bytes).
- `OwnerCapability.token()` returns the raw capability encoded as a bearer token (`containment.py:140-141`).
- The real CLI accepts `--owner-secret` (`containment.py:949-951`), exposing it through process arguments; it also accepts the environment fallback.
- The repository test helper itself passes `CAP.secret` on the command line, demonstrating the unsafe interface shape.

`repr()` is redacted and equality intentionally excludes the secret, but those mitigations do not contain the bearer credential. A caller-declared `issuer` or a raw CLI secret is not an acceptable Release Authority boundary.

Required fix: remove public raw-secret/token extraction and raw secret CLI arguments; use a secure owner-issued capability handle or protected file descriptor/IPC boundary. Keep secret comparison cryptographically correct where capability comparison is needed, make the secret storage private, define safe provisioning/lifecycle and file permissions, and ensure no process listing, repr, JSON, logs, test fixtures, or dataclass operations expose it.

### 6. Authenticated head schema relationships are incomplete

The head validator checks field shapes and its HMAC, but does not bind `operation` to the cursor/journal record transition. I changed an authenticated head after issue to `operation="genesis"`, `request_digest=null`, recomputed its valid HMAC with the provisioned capability, and both API and real CLI accepted it:

```text
malformed_authenticated_head committed 1 active
cli_malformed_head 0 {"decision": "ALLOWED", ...} False
```

Genesis must be exactly cursor 0 with the genesis digest and empty receipt; a committed cursor-1 head cannot be a genesis transition. The validator also accepts `schema_version=True` because `True == 1`, contrary to exact stored-type validation.

Required fix: validate every head relationship and exact scalar type, including operation-to-record/request/current-receipt binding, genesis invariants, and strict boolean rejection. Keep all malformed states typed and traceback-free through the real CLI.

## Requirement and prior-finding disposition

- Valid-prefix rollback: journal-only and head-only rollback refuse; rollback of both default files authorizes, so the requirement fails.
- Missing/corrupt/stale/ahead/mismatched/pending head: ordinary current-state paths fail closed for the covered cases; exact pending recovery works for a fully readable candidate/base. The destructive pending-write and torn-reconcile cases above fail the full requirement.
- Crash coverage: lock and ordinary fsync cases are typed in the repository suite, but partial pending writes, pending close, final backstop failure, and reconcile append ambiguity expose unsafe or irrecoverable states.
- Duplicate semantics: the pass-4 divergent same-ID and post-termination reproductions are closed in the ordinary path; identical active duplicates are idempotent. This does not cure the ambiguity-to-success case above.
- Receipt/journal schema: pass-4 malformed receipt and terminate-record regressions pass, and strict receipt/revision/content/record hashes, TTL, timestamps, fixed effects/read class/policy, audit path, and reconcile field sets are substantially enforced. Head relationships remain incomplete, and full crash recovery is not proven.
- Owner authentication/secrets: HMAC verification protects an existing correctly provisioned head, but provisioning and runtime wiring do not create an enforceable production boundary, and the public/CLI secret surfaces are release blockers.
- Distinct CLI trust domain: fails; no CLI anchor-path option exists and the default is adjacent to the journal.
- Provisioning: `provision_owner_anchor()` is callable by arbitrary Python code with an arbitrary newly generated capability and can create an empty canonical store. There is no accepted Release Authority provisioning boundary in this commit, and the CLI has no one-time authorized provisioning flow. It rejects existing journal/head files but cannot prevent an arbitrary caller from minting a new authority at an empty canonical path.
- Current-state reads: `check()` calls `_current_state()` each time; no receipt/cache/marker bypass was found. `verify_containment` has zero repository references.
- Races: the repository’s 104-test authority/acceptance suite passed; I independently repeated the separate-process race test 10/10. This is not evidence against the persistence and trust-boundary failures.
- Hygiene/scope: `compileall`, `git diff --check`, exports, and scope audit pass. The pinned commit changes only `containment.py`, `run_authority/__init__.py`, and its tests; no cloud/legacy mutation path was introduced.

## Verification performed

```text
pytest -q tests/arnold_pipelines/run_authority tests/run_authority tests/cloud/test_m1_containment_acceptance.py
104 passed in 10.21s

independent separate-process race repetitions: 10/10
python -m compileall -q arnold_pipelines/run_authority: passed
git diff --check: passed
verify_containment search: zero references
```

The passing repository tests do not make this commit release-candidate quality because the counterexamples above are outside their coverage and violate the stated T0.0 contract.

## Required disposition

Do not accept or release this commit. Repair the six blockers, add deterministic regressions for each minimal reproduction and every persistence boundary, rerun a fresh independent review, and only then reassess local candidacy.

Even after code repair, T0.0 is not complete until the accepted Release Authority deploys the implementation, provisions the owner anchor/capability off-volume, runs the exact approved runtime tuple, and supplies a real owner-issued cloud containment receipt. This local adapter is not itself a live cloud containment decision.
