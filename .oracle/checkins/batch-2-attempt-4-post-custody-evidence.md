# Batch-2 attempt-4 post-custody Luna evidence/authenticity review

## Review boundary and identity

Fresh independent read-only GPT-5.6 Luna/high review of the reconciled target
`/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4`, branch
`reconcile/nbf-attempt4-2297`. The review inspected the reconciled source,
tests, frozen references, custody receipt, sealed manifest, and the bound
attempt-4 executor artifacts. No source, test, frozen document, status,
history, custody, index, or prior artifact was edited. No model was launched,
no delegation was used, and no implementation change was issued.

The original custody-drift attempt-4 evidence/authenticity, runtime, and
authority review outputs were explicitly excluded. In particular, the
pre-reconciliation review check-ins and receipts under the original worktree
were not consumed as review evidence. The executor finding/receipt and the
v2/v3 evidence corrections were consumed only as historical claims and were
independently rechecked against the reconciled tree and fresh captures.

Fresh capture root: `.oracle/evidence/batch-2-attempt-4-post-custody-evidence/`.
Every command record is a JSON file in that root. Each record contains the
literal argv, exact probe body when applicable, repository cwd, UTC start/end,
exit code, separate stdout/stderr byte counts and SHA-256 values, and pre/post
porcelain, HEAD, branch, frozen-file hashes, and index state. Candidate
full/production diff hashes are explicit in the diff records and in the
complete post-write custody state record.

## Custody and byte identity

The fresh captures establish:

- HEAD: `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`.
- Branch: `reconcile/nbf-attempt4-2297`.
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- Candidate implementation: `5da26ec5be4d13559948fe4256a114ad7626482b`.
- Full source/test diff: 153829 bytes,
  `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163`.
- Production diff: 109379 bytes,
  `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32`.
- The candidate source/test path inventory contains 21 modified tracked paths;
  no untracked production/test path was found.
- The index was unstaged at the pre-write audit and remains unstaged in every
  command record. Review evidence files are untracked by design.

The tasklist, North Star, goal, status, and custody files were rehashed. The
North Star, tasklist, goal, status, and custody hashes match the supplied
bindings. `.oracle/plan.md` is absent in this reconciled target: the direct
six-file `shasum` command exited 1, with the missing path reported on stderr.
This is an evidence-bound discrepancy: the user-supplied plan hash cannot be
recomputed from this target, and the custody-reconciliation receipt explicitly
lists the plan among excluded files. The sealed manifest's historical claim
that the plan hash was checked therefore cannot substitute for a current target
file.

The sealed attempt-4 manifest was read and its canonical identity is internally
consistent as a historical evidence seal: 70 captured files excluding the
manifest, 6213 manifest bytes, and manifest SHA-256
`7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e`. That seal
is not treated as implementation proof or as a batch disposition.

## Fresh executable evidence

All focused commands were rerun with `PYTHONPATH` bound to the reconciled
repository so the package under review, rather than an installed neighboring
checkout, was imported. The fresh local-package results were:

| Root | Result | Capture |
|---|---|---|
| R3-NATIVE-001 focused | 4 passed, exit 0 | `21-local-r3-native-focused.*` |
| R3-TERM-002 focused | 5 passed, exit 0 | `22-local-r3-term-focused.*` |
| R3-LIFE-003 focused | 5 passed, exit 0 | `23-local-r3-life-focused.*` |
| R3-AUTH-004 focused | 5 passed, exit 0 | `24-local-r3-auth-focused.*` |
| authority module | 14 passed, exit 0 | `25-local-authority-full-module.*` |
| checker `--check` | `ok: true`, exit 0 | `26-local-authority-check.*` |
| independent raw-symbol scan | zero matches, exit 0 | `29-independent-raw-symbol-scan.*` |

The initial unqualified Python probe imported
`/Users/peteromalley/Documents/Arnold/arnold_pipelines/...`, not this target;
that probe is retained as a provenance warning, not as candidate evidence.
The corrected local-package probes are the authoritative fresh probes.

## Source findings by frozen rework root

### R3-NATIVE-001 — construction seam remains attestation-shaped

The candidate's `_native_construction_proof` in
`arnold_pipelines/megaplan/workers/_impl.py:7349-7401` selects a callable
(`run_codex_step` or `run_claude_step`), checks a model-name prefix, and builds a
proof whose registry records the callable's module and qualname. It does not
invoke the constructor or obtain proof from the selected backend/runtime/model
construction seam. The production request installs this function as
`native_construction_seam` at `:7469-7471`; admission therefore receives a
self-generated callable description, not an actual construction result.

Fresh local probe `19-native-seam-local-authority-probe.stdout` replaced
`run_codex_step` with a function that would raise if invoked. The candidate
returned `{'constructable': True, 'constructor_calls': 0,
'constructor': '__main__:forbidden'}`. This is direct positive evidence that a
proof can admit without crossing the native construction seam. The focused test
passes because its `native_proof()` helper is an arbitrary test-created mapping
(`tests/cloud/dispatch_test_helpers.py:8-34`), and
`test_native_selected_construction_seam_admits_exactly_once` counts callback
invocations, not construction. Consequently exact content/generation,
registry/family, route/provider, age, and digest checks are checks over a
caller-provided proof rather than recomputed proof from actual construction.
The `proof.constructable is True` check is present but does not repair that
authority gap.

### R3-TERM-002 — generic transport passes; real native phase transport is lossy

The generic focused parameterization in
`tests/cloud/test_worker_dispatch_spy.py:94-125` uses the same direct
`dispatch_with_admission` call for labels `native`, `omp`, and `managed`; it
does not invoke `run_step_with_worker`, `_run_omp_with_admission`, or
`_admit_managed_launch`. It is therefore not a real-door matrix.

The real native path in `_production_worker_dispatch`
(`workers/_impl.py:7476-7502`) returns the WBC worker result, which is the
legacy four-tuple. In `dispatch_with_admission`, `return_worker=True` returns
that raw tuple (`cloud/worker_dispatch.py:1166-1173`). The metadata attachment
branch only runs when the raw value has `auth_metadata`; a tuple has no such
attribute. `handlers/shared.py:1045-1050` reads `worker.auth_metadata` to
populate `response["dispatch_outcome"]`. Thus the canonical terminal event
can be persisted while the real native phase response loses the typed outcome.
Fresh local probe `30-tuple-terminal-transport-probe.stdout` observed
`{'result_type': 'tuple', 'tuple_len': 4, 'worker_auth_metadata': None,
 'terminal_count': 1}`.

There is a second identity weakness in the same normalization path:
`_worker_identity()` falls back to the dispatch process identity when a real
WorkerResult has no worker identity (`cloud/worker_dispatch.py:787-790`), while
normal tuple projection supplies `getattr(worker, "worker_identity", None)`
(`:918-922`). The WorkerResult definition has no `worker_identity` field
(`workers/_impl.py:2312-2346`). A successful real native tuple can therefore
record the dispatcher identity instead of the worker identity. The generic
fixture supplies a typed identity directly and does not exercise this path.

The source does preserve useful typed checks: `_validate_outcome_context`
compares receipt/fingerprint/phase/spec/dispatch identities, failure-shaped
WorkerResult values are rejected without a typed envelope, and terminal append
failure returns an unresolved outcome. Those positives do not establish the
required real-door, end-to-end lossless transport.

### R3-LIFE-003 — accepted-first persisted history is still accepted

`incident/ledger.py:40-96` claims global matrix validation, but the loop has an
explicit compatibility exception at `:80-84`: when the first persisted state is
`accepted`, it sets `highest = rank` and continues. This directly permits
`accepted` without `not_started` and `entered`. `ControlledFinalLaunch` also
restores a strongest marker after calling projection
(`cloud/controlled_final_launch.py:42-65`), so the reopen path does not add a
stricter boundary.

Fresh local probe `20-lifecycle-accepted-first-probe.stdout` created a valid
reservation, appended only an `accepted` controlled-adapter marker, and called
`projection()`. It returned `{'accepted_first': True, 'accepted_launch': True}`
with exit 0. This contradicts the frozen requirement to reject
accepted-before-entered globally. The five lifecycle focused tests do not cover
this direct persisted accepted-first history.

### R3-AUTH-004 — checker still depends on configured-path scope mode

The authority module and repository `--check` are green, and the independent
raw-symbol scan found no `refresh_runtime_launch_seed_for_worker_dispatch` or
`require_configured_runtime_launch` occurrences in the three configured doors.
Those are positive structural results only.

`check_worker_admission_authority.py:184-193` sets `door_scope` from the
function spelling unless `strict_all_calls` is true. `check_files()` passes
`strict_all_calls=path not in DOORS` (`:318-333`). Therefore a configured door
file is still name-filtered. Fresh local probe
`28-checker-configured-spelling-probe-2.stdout` supplied a configured door
containing only `def unrelated(): subprocess.Popen(...)`; the checker returned
`{'ok': True, 'categories': []}`. The same checker catches that fixture when it
is treated as an unconfigured temporary path, confirming the mode-dependent
false negative. This violates the frozen requirement to inspect every call in
configured door files independently of enclosing-symbol spelling, even though
the repository's current source happens not to contain that particular hidden
call.

## Evidence/authenticity assessment

The candidate diff identities and frozen files that exist in the target are
recomputed and bound. The sealed historical capture chain is internally
consistent, and the fresh focused test streams are reproducible against the
local package. However, green tests are not sufficient proof here: the native
construction test is resolver/callback-shaped, the terminal matrix is a generic
lambda fixture, the lifecycle matrix omits accepted-first persisted state, and
the checker green result does not exercise configured arbitrary symbols.

The four roots therefore retain concrete source-level contradictions or
unproven authority boundaries listed above. The absent `.oracle/plan.md` also
prevents byte-level reauthentication of the full frozen-plan binding in this
reconciled target. No batch disposition is issued by this check-in.

## Fresh output boundary

This check-in and its paired receipt are the only review outputs. The receipt
contains the complete command-record index, capture hashes, candidate pre/post
identities, consumed-file rehash result, and the post-write output inventory
reference. Fresh output hashes are finalized in the post-write inventory under
the unique evidence root and are intentionally not copied into the files being
hashed to avoid self-referential digest cycles.
