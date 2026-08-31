# Batch-2 attempt-4 post-custody Luna evidence/authenticity receipt

## Session and boundary

- Model: `openai-codex/gpt-5.6-luna`; fresh independent high-reasoning session.
- Lens: evidence/authenticity only.
- Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4`.
- No subagent, nested model, implementation change, commit, stage, push, merge,
  Batch-3 action, or mutable harness action was used.
- Review outputs: this receipt and
  `.oracle/checkins/batch-2-attempt-4-post-custody-evidence.md` only.
- All command captures and probe bodies are under
  `.oracle/evidence/batch-2-attempt-4-post-custody-evidence/`.

The original custody-drift attempt-4 evidence/authenticity, runtime, and
authority reviews were excluded and were not used as review evidence. The
executor finding/receipt, v2/v3 correction pair, custody-reconciliation receipt,
and sealed manifest were historical inputs only; their claims were rehashed and
checked against fresh source and probes.

## Candidate and frozen identity proof

Observed and recomputed:

- HEAD `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`.
- Branch `reconcile/nbf-attempt4-2297`.
- Source base `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- Candidate implementation `5da26ec5be4d13559948fe4256a114ad7626482b`.
- Full source/test diff: 153829 bytes,
  `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163`.
- Production diff: 109379 bytes,
  `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32`.
- Source/test inventory: 21 modified tracked paths and no untracked paths under
  `arnold_pipelines`, `scripts`, or `tests`.
- Index: unstaged; `git diff --cached --name-status` exits 0 with empty output.

The full and production diff streams are retained as
`07-full-diff.stdout` and `08-production-diff.stdout`; their command records
contain the exact argv, UTC intervals, exits, and paired stream digests. The
complete post-write custody state, including pre/post candidate full and
production diff hashes, is record `36-post-write-custody-state-complete.json`.
Its pre/post snapshots have the same HEAD, branch, frozen-file hashes, and
empty staged-name output as the initial identity capture. The only additions
visible there are review evidence captures and pre-existing untracked Oracle
artifacts; source/test paths remain the reconciled candidate patch.

Frozen files rehashed by `06-frozen-hashes.json` and its streams:

- tasklist: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`;
- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`;
- goal: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`;
- status: `9f4c6a0794a87d18aaac3e49109baa7ed792d86571483913625ebc1507e362af`;
- custody: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`;
- `.oracle/plan.md`: absent; the six-file shasum command exits 1 and records the
  missing path on stderr.

The plan absence is not repaired or treated as equivalent to the supplied
hash. The custody-reconciliation receipt explicitly excluded that file, so the
frozen-plan binding cannot be reauthenticated from this target. The supplied
North Star block is byte-identical to the target file.

## Consumed artifact rehash

`31-consumed-file-hashes.json` and `31-consumed-file-hashes.stdout` contain the
complete SHA-256 output for every existing consumed frozen artifact, packet,
brief, finding, receipt, sealed manifest, custody/policy receipt, inspected
source module, checker, and focused test. It exited 0 for those existing paths.
Record 06 is the separate negative proof for the missing plan. The sealed
historical manifest was read and its reported identity is 70 files excluding
the manifest, 6213 bytes, SHA-256
`7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e`; it is not
implementation proof or a review disposition.

## Complete command evidence

The evidence root contains complete JSON records for every subprocess command.
Each record contains literal argv/body, cwd, UTC start/end, exit, separate
stdout/stderr counts and SHA-256 values, and pre/post status, HEAD, branch,
frozen-file hashes, and index state. Candidate full/production diff hashes are
explicit in records 07/08 and in the complete pre/post state record 36.

The paired `.stdout` and `.stderr` files are retained for every record. The
following index names the command records through the final custody audit;
later output-hash records are named explicitly after it. The JSON files are the
authoritative literal command records (so multiline probe bodies are not
paraphrased here):

`01-identity`, `02-head`, `03-branch`, `04-candidate-show`, `05-base-show`,
`06-frozen-hashes`, `07-full-diff`, `08-production-diff`, `09-source-test-paths`,
`10-r3-native-focused`, `11-r3-term-focused`, `12-r3-life-focused`,
`13-r3-auth-focused`, `14-authority-full-module`, `15-authority-check`,
`16-native-seam-authority-probe`, `17-native-symbol-probe`,
`18-native-symbol-local-probe`, `19-native-seam-local-authority-probe`,
`20-lifecycle-accepted-first-probe`, `21-local-r3-native-focused`,
`22-local-r3-term-focused`, `23-local-r3-life-focused`, `24-local-r3-auth-focused`,
`25-local-authority-full-module`, `26-local-authority-check`,
`27-checker-configured-spelling-probe`, `28-checker-configured-spelling-probe-2`,
`29-independent-raw-symbol-scan`, `30-tuple-terminal-transport-probe`,
`31-consumed-file-hashes`, `32-pre-write-final-audit`, `33-post-write-final-audit`,
`34-post-write-output-hashes`, `35-post-write-output-hashes-final`,
`36-post-write-custody-state-complete`.

The initial unqualified Python probe is intentionally retained as a provenance
warning: it imported the neighboring installed checkout
`/Users/peteromalley/Documents/Arnold`. The corrected records 18, 19, 20, 28,
30 and all `local-*` test records set `PYTHONPATH` to this reconciled target.
Only those corrected records are used for candidate behavior claims.

Selected fresh stream identities:

| Record | Exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 |
|---|---:|---|---|
| 06 frozen hashes | 1 | 430 / `8fd8d6c4ada660697888c95a2dfe7ad0e17dfad96dd1e20735b3634692852c93` | 51 / `1f701b5785e00f4aef2a6588e0e41dd3d4d502d3bda823f69313907d43af3c72` |
| 07 full diff | 0 | 153829 / `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 08 production diff | 0 | 109379 / `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 19 native seam local | 0 | 85 / `c2cc342b1782c3549be6e2c00a68c3c2a2e49098cb02045fbf331fe44b91224a` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 20 lifecycle accepted-first | 0 | 50 / `cd6d887747e514b8757391a9eb208b374a694a9508618ed54b17314c7e5a078f` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 21 local native focused | 0 | 98 / `006ba2e6e18954ad086677bc060e3290380048985a443818578f6ef51ed1b21b` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 22 local terminal focused | 0 | 98 / `dc73d5669fe02105037ac272969a74c0e92d8e4eda11ab9f36efd14f0fd1c648` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 23 local lifecycle focused | 0 | 98 / `1966890ba6efc09f86dd998039477f6271ab6aa52cc7ff72888f7d6b6a9bc479` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 24 local authority focused | 0 | 98 / `31aea369e724e06e40899f30e41b4d08322eb801791b7267f074241d775f0735` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 25 authority module | 0 | 100 / `788c46c655c7b12a4719c8b344382d9e3ce98d541f9136fb0dfdbc151384e469` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 26 checker | 0 | 213 / `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 28 configured spelling | 0 | 31 / `7aca096088eb0943a1ac2c2c59eba92cf049ac106df13dc1b6b039ddbf75d64c` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 29 raw-symbol scan | 0 | 28 / `f093f6e2fa89720a6456e1211c3eb3d79bfe40a973c872785b680b90d2db2c8d` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 30 tuple transport | 0 | 92 / `9b5e12aa2ae76bc53afd99008b933902c5dd9254b38cb1c9d67cca9cf7a9b4a9` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 32 pre-write audit | 0 | 31572 / `0f9131f456d0f73d86bcb4b312fe1d3152a0f73048fd4d39195c07acb5069adb` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

For records not repeated in this table, the complete byte/hash values remain in
the named JSON and paired stream files; no command is omitted from the index.

## Review evidence references

- Native proof: `19-native-seam-local-authority-probe.stdout` reports
  `constructable=True`, `constructor_calls=0`, and constructor `__main__:forbidden`.
  The source path is `workers/_impl.py:7349-7401`; production wiring is
  `:7469-7471`. The proof describes a callable but never invokes the selected
  backend/runtime/model constructor.
- Terminal transport: `30-tuple-terminal-transport-probe.stdout` reports
  `result_type=tuple`, `tuple_len=4`, `worker_auth_metadata=None`, and
  `terminal_count=1`. The real native path returns the WBC legacy tuple at
  `workers/_impl.py:7476-7502`; `dispatch_with_admission` attaches metadata only
  to objects with `auth_metadata` at `cloud/worker_dispatch.py:1166-1173`, while
  `handlers/shared.py:1045-1050` consumes that metadata.
- Lifecycle: `20-lifecycle-accepted-first-probe.stdout` reports
  `accepted_first=True` and `accepted_launch=True`. The compatibility branch in
  `incident/ledger.py:80-84` accepts an initial `accepted` marker, contrary to
  the global persisted matrix.
- Checker: `28-checker-configured-spelling-probe-2.stdout` reports
  `ok=True, categories=[]` for a configured door whose unrelated function calls
  `subprocess.Popen`. `check_worker_admission_authority.py:184-193,318-333`
  still enables function-name scope for configured `DOORS`.
- Positive but insufficient checks: records 21–26 pass the fresh local focused
  tests, full authority module, and `--check`; record 29 finds no forbidden raw
  symbols. The generic terminal test remains a direct lambda fixture rather
  than a real native/OMP/managed-door exercise.

The paired check-in contains the complete source-based assessment and explicitly
records these four root-level authority gaps. No batch disposition is issued by
this receipt.

## Post-write output hash contract

The post-write inventory records the SHA-256, byte count, and final-newline
status of this check-in and receipt, every command JSON/stream, every probe
body, and every other regular capture file. Those final output hashes are
externalized in the inventory to avoid an impossible self-referential receipt
digest; the final check-in and receipt hashes are recorded there as
`EXTERNAL/` entries.
