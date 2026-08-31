# Batch-2 attempt-4 v3 Luna receipt-only correction

## Receipt authority and boundary

This is an executor evidence-integrity correction receipt only. It is not
implementation, test evidence, review, Oracle adjudication, or a Batch-2
verdict. It corrects one stale paragraph in the immutable attempt-4 v2
receipt. It does not alter, validate, or reinterpret the candidate.

The operator launch metadata below is recorded for provenance only. It was not
run by this executor:

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-batch-2-attempt-4-v3-luna.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=900
```

No model was invoked or nested. No test was rerun. No review or adjudication was
performed.

## Immutable binding ledger

| Binding | Identity |
|---|---|
| repository / branch | `/Users/peteromalley/Documents/Arnold-oracle-nbf` / `megado-nbf-guard-0826` |
| current HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| candidate implementation | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| candidate parent / tree | `19deab5bb407273e7e82d40a66fc06d17af93ad4` / `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| candidate full source/test diff | 153829 bytes; `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` |
| candidate production-only diff | 109379 bytes; `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` |
| attempt-4 packet | `.oracle/rework/batch-2-attempt-4.md`; `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078` |
| attempt-4 executor brief | `.oracle/briefs/execution-batch-2-attempt-4-luna.md`; `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9` |
| v2 finding | `.oracle/findings/execution-batch-2-attempt-4-v2-luna.md`; `dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff` |
| v2 receipt, stale identity | `.oracle/receipts/execution-batch-2-attempt-4-v2-luna.md`; `130e1e35883b16738718c46e13f6229b23a64184777790e5a755e791916ef831` |
| v2 final-seal gap receipt | `.oracle/receipts/execution-batch-2-attempt-4-v2-final-seal-gap.md`; `7a1d548d73808a317847f5ae25fe236fb4d93b646836f72fcefcc95efdf28299` |
| frozen tasklist | `.oracle/tasklist.md`; `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| frozen North Star | `.oracle/northstar.md`; `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| frozen plan / goal / custody | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` / `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |

## Corrected final manifest identity

Preserved evidence root, inspected without modification:

`/tmp/arnold-b2-attempt4-v2-luna-evidence.cLNWAe/`

Canonical manifest path:

`/tmp/arnold-b2-attempt4-v2-luna-evidence.cLNWAe/manifest.sha256`

The independent recomputation followed the v2 final-seal gap definition:
include every regular file except `manifest.sha256`; spell each path relative to
the evidence root with POSIX separators; emit `<sha256><two spaces><relative
path><newline>`; sort complete lines bytewise by relative path; preserve the
final newline; hash the exact manifest bytes with SHA-256.

Verified result:

- regular captures excluding the manifest: `70`;
- regular files including the manifest: `71`;
- exact manifest bytes: `6213`;
- exact manifest SHA-256:
  `7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e`;
- recomputed bytes: `6213`;
- recomputed SHA-256:
  `7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e`;
- recomputation byte-identical to the preserved manifest: `true`;
- final newline: present.

The earlier v2 receipt's `65`-file / `5760`-byte /
`70fc93c723420d9ea4ab54123411dd6ea11d492ea56763cd964cfaaffadf54e0` identity
is stale only and is superseded by the identity above. The v2 finding's
70-file final identity is corroborated. This correction adds no new
implementation or test evidence.

### Independent checksum check

`shasum -a 256 -c manifest.sha256` was run from the evidence root independently.
It exited `0`; stdout contained `70` `OK` lines and zero `FAILED` lines; stderr
was empty.

- stdout: `1873` bytes; SHA-256
  `2f203c4e0a0337078578131158a72b16158ea51436471fdc12924fede99ea95c`;
- stderr: `0` bytes; SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## North Star byte check

The canonical North Star block supplied in the correction brief was extracted
as the block content between the supplied marker lines, including its terminal
newline, and compared byte-for-byte with `.oracle/northstar.md`.

- expected bytes: `1515`;
- file bytes: `1515`;
- expected SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`;
- file SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`;
- byte-identical: `true`;
- final newline: `true`.

## Exact read-only command records

All records below use UTC timestamps, separate captured streams, and the
repository cwd `/Users/peteromalley/Documents/Arnold-oracle-nbf` unless another
cwd is stated. Python command records use the exact executable path shown in
`argv` and the exact `-c` body shown below. No command below writes the
preserved evidence root.

### Manifest recomputation

- start: `2026-08-30T21:31:34.530493Z`;
- end: `2026-08-30T21:31:36.366943Z`;
- exit: `0`;
- argv:
  `[`"`/Users/peteromalley/.pyenv/versions/3.11.11/bin/python`"`, `"-c"`,
  `<body>`]`;
- stdout: `264` bytes; SHA-256
  `faa561ef5fd72620e17e50b3b41b11e2f49f650ec85fd675b38f7a99541ba8af`;
- stderr: `0` bytes; SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Exact `-c` body:

```python
import hashlib, json, pathlib, subprocess
r=pathlib.Path("/tmp/arnold-b2-attempt4-v2-luna-evidence.cLNWAe").resolve(); m=r/"manifest.sha256"
paths=sorted((p.relative_to(r).as_posix() for p in r.rglob("*") if p.is_file() and p != m), key=lambda p:p.encode("utf-8")); lines=[]
for rel in paths:
 p=subprocess.run(["shasum","-a","256",rel],cwd=r,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE); lines.append(p.stdout.split()[0].decode()+"  "+rel+"\n")
data="".join(lines).encode(); actual=m.read_bytes(); print(json.dumps({"count":len(paths),"bytes":len(actual),"sha256":hashlib.sha256(actual).hexdigest(),"recomputed_bytes":len(data),"recomputed_sha256":hashlib.sha256(data).hexdigest(),"identical":data==actual,"final_newline":actual.endswith(b"\n")},sort_keys=True))
```

### Independent `shasum -c`

- cwd:
  `/tmp/arnold-b2-attempt4-v2-luna-evidence.cLNWAe`;
- start: `2026-08-30T21:31:36.367108Z`;
- end: `2026-08-30T21:31:36.398554Z`;
- exit: `0`;
- exact argv: `[`"`shasum`"`, `"-a"`, `"256"`, `"-c"`,
  `"manifest.sha256"`]`;
- stdout: `1873` bytes; SHA-256
  `2f203c4e0a0337078578131158a72b16158ea51436471fdc12924fede99ea95c`;
- stderr: `0` bytes; SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

### North Star canonical comparison

- start: `2026-08-30T21:32:31.311793Z`;
- end: `2026-08-30T21:32:31.407972Z`;
- exit: `0`;
- argv:
  `[`"`/Users/peteromalley/.pyenv/versions/3.11.11/bin/python`"`, `"-c"`,
  `<body>`]`;
- stdout: `262` bytes; SHA-256
  `b631e4e1c5b4e509c7fb7bbe8c3cfbb5d2b1637e8fa46520ca0b14f75cdbda75`;
- stderr: `0` bytes; SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Exact `-c` body:

```python
import hashlib,json
from pathlib import Path
actual=Path(".oracle/northstar.md").read_bytes()
expected="""# North Star — Arnold self-healing supervision

**End state:** An agent harness where no worker can be launched onto a spec that
isn't live, a box that won't survive it, or a seed bound to the wrong interpreter —
and where every worker death carries its killer's identity in a typed record that
the recovery loop consumes before it ever retries the same fingerprint.

**Enduring principles**
- One door per invariant: admission, dispatch, and death are each enforced at
  exactly one place; duplicate preflights are deleted, not patched around.
- Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits
  `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
- Models are admitted, not assumed: a model id must resolve against catalog,
  prefix map, family classifier, and live provider membership at dispatch time,
  typedly rejecting expired or unknown ids.
- Fixes ship on main through the fixer contract; hotfixes that live only as
  deployed-but-uncommitted files do not exist.

**Anti-patterns to avoid**
- Single-scan verdicts treated as sustained truth (wedge kills, restacks).
- Anonymous integer exit codes where a disposition belongs.
- Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
- Redispatch of an identical failure fingerprint without a changed precondition.

**Aligned progress feels like:** fewer incident classes over time, each new stall
arriving with evidence attached and leaving with a root fix on main.
""".encode()
print(json.dumps({"file_bytes":len(actual),"expected_bytes":len(expected),"file_sha256":hashlib.sha256(actual).hexdigest(),"expected_sha256":hashlib.sha256(expected).hexdigest(),"byte_identical":actual==expected,"final_newline":actual.endswith(b"\n") and expected.endswith(b"\n")},sort_keys=True))
```

The comparison stdout was:

```text
{"byte_identical": true, "expected_bytes": 1515, "expected_sha256": "d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e", "file_bytes": 1515, "file_sha256": "d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e", "final_newline": true}
```

### Pre-write porcelain and index proof

These commands were run before either v3 artifact was written. Their exact
argv, cwd, UTC interval, exit, and separate stream digests were:

| record | exact argv | start–end UTC | exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 |
|---|---|---|---:|---|---|
| `git-status-pre-final` | `git status --porcelain=v1` | `2026-08-30T21:31:15.330894Z–2026-08-30T21:31:15.417593Z` | 0 | 5347 / `c52d31448de356fcdc23c2b4612891a40530dc552c3a0a510cdacc390edb6cf3` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git-index-quiet-pre-final` | `git diff --cached --quiet` | `2026-08-30T21:31:15.417659Z–2026-08-30T21:31:15.436188Z` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git-index-name-status-pre-final` | `git diff --cached --name-status` | `2026-08-30T21:31:15.436261Z–2026-08-30T21:31:15.460836Z` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The pre-write index was empty and clean. The pre-write porcelain was already
dirty with the unrelated candidate and prior untracked artifacts; this receipt
does not attribute those paths to this correction.

## Preserved capture-root inventory

The root contains these 71 regular files. The manifest input set is this list
with `manifest.sha256` removed, hence 70 captures:

```text
clean-archive.json
clean-archive.post-porcelain
clean-archive.pre-porcelain
clean-archive.sh
clean-archive.stderr
clean-archive.stdout
clean-pytest.json
clean-pytest.post-porcelain
clean-pytest.pre-porcelain
clean-pytest.sh
clean-pytest.stderr
clean-pytest.stdout
head-renderer.json
head-renderer.post-porcelain
head-renderer.pre-porcelain
head-renderer.sh
head-renderer.stderr
head-renderer.stdout
identity-final.json
identity-final.post-porcelain
identity-final.pre-porcelain
identity-final.stderr
identity-final.stdout
identity-post.json
identity-post.post-porcelain
identity-post.pre-porcelain
identity-post.stderr
identity-post.stdout
identity-pre.json
identity-pre.post-porcelain
identity-pre.pre-porcelain
identity-pre.stderr
identity-pre.stdout
identity.sh
manifest-build.json
manifest-build.post-porcelain
manifest-build.pre-porcelain
manifest-build.sh
manifest-build.stderr
manifest-build.stdout
manifest-recompute.json
manifest-recompute.post-porcelain
manifest-recompute.pre-porcelain
manifest-recompute.sh
manifest-recompute.stderr
manifest-recompute.stdout
manifest.sha256
parent-diff.json
parent-diff.post-porcelain
parent-diff.pre-porcelain
parent-diff.sh
parent-diff.stderr
parent-diff.stdout
parent-hashes.json
parent-hashes.post-porcelain
parent-hashes.pre-porcelain
parent-hashes.sh
parent-hashes.stderr
parent-hashes.stdout
parent-renderer.json
parent-renderer.post-porcelain
parent-renderer.pre-porcelain
parent-renderer.sh
parent-renderer.stderr
parent-renderer.stdout
raw-symbol.json
raw-symbol.post-porcelain
raw-symbol.pre-porcelain
raw-symbol.sh
raw-symbol.stderr
raw-symbol.stdout
```

## Correction-only non-actions and disposition

No source, test, frozen document, status, history, custody, tasklist, North Star,
plan, goal, or git-index content was edited, deleted, rewritten, staged, or
committed. The evidence root was not written or repaired. Prior v2 artifacts and
the v2 final-seal gap receipt were not changed. No test rerun, model launch,
nested model, review, commit, stage, push, merge, reset, or Batch-3 action
occurred. No implementation or test claim is added here.

The only files written by this correction are:

- `.oracle/findings/execution-batch-2-attempt-4-v3-luna.md`;
- `.oracle/receipts/execution-batch-2-attempt-4-v3-luna.md`.

The earlier v2 receipt is stale only. The corrected identity is bound above; a
later gate must consume this receipt and a fresh seal. This receipt issues no
batch disposition.

## Audit note

One preliminary read-only print used an incorrectly escaped newline predicate
and reported `final_newline: false`; it did not modify the evidence root and was
not used as a result. A direct trailing-byte check and the subsequent canonical
byte comparison both observed the terminal byte `0x0a` and `final_newline: true`.
The corrected records above are the controlling evidence.
 
## Post-write porcelain and index proof

After both v3 artifacts were written, the same read-only porcelain and index
commands were run. The post-write index remained empty and clean. The only
additional porcelain entries are the two named v3 artifacts.

| record | exact argv | start–end UTC | exit | stdout bytes / SHA-256 | stderr bytes / SHA-256 |
|---|---|---|---:|---|---|
| `git-status-post` | `git status --porcelain=v1` | `2026-08-30T21:34:50.164676Z–2026-08-30T21:34:50.389174Z` | 0 | 5465 / `ccf14b9e953d4556ca1c508f1028513d8337a9a50c377deb2ea98fd04c9bddb2` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git-index-quiet-post` | `git diff --cached --quiet` | `2026-08-30T21:34:50.389429Z–2026-08-30T21:34:50.426617Z` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git-index-name-status-post` | `git diff --cached --name-status` | `2026-08-30T21:34:50.426932Z–2026-08-30T21:34:50.465042Z` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The pre/post status stream digests differ only by the two newly written v3
paths; all prior dirty paths remained present. The index proof is unchanged:
zero staged paths and `git diff --cached --quiet` exit `0` both before and
after.
