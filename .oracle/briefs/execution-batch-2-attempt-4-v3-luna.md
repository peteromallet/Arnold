# Batch-2 attempt-4 v3 — Luna receipt-only correction brief

## Hard boundary

This is a minimal evidence-integrity correction for the attempt-4 v2 receipt.
It is not implementation, review, Oracle adjudication, or a Batch-2 verdict.
Do not edit, delete, or rewrite any prior artifact. Do not edit source, tests,
frozen documents, status, history, custody, tasklist, North Star, plan, goal,
or the git index. Do not rerun tests, invoke another model, delegate, commit,
stage, push, merge, reset, or start Batch 3. The candidate and all existing
evidence captures must remain unchanged.

Create only these append-only artifacts:

- .oracle/findings/execution-batch-2-attempt-4-v3-luna.md
- .oracle/receipts/execution-batch-2-attempt-4-v3-luna.md

The finding must say this is a receipt correction only. The receipt must
independently recompute and bind the final evidence-manifest identity. Neither
artifact may issue PASS_BATCH_2 or ACCEPTED_ISSUES.

The operator launch metadata, which must not be run by the executor, is exactly:

    PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-batch-2-attempt-4-v3-luna.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=900

## Immutable bindings

| Binding | Identity |
|---|---|
| Repository / branch | /Users/peteromalley/Documents/Arnold-oracle-nbf / megado-nbf-guard-0826 |
| Current HEAD | 2297fb330cdb375b4e5bd048f0d5c37d0e06db30 |
| Source/base | origin/main@798c50619204010ed3f4297fbb57988fe9381924 |
| Candidate implementation | 5da26ec5be4d13559948fe4256a114ad7626482b |
| Candidate full source/test diff | 153829 bytes; 67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163 |
| Candidate production-only diff | 109379 bytes; 009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32 |
| Attempt-4 packet | .oracle/rework/batch-2-attempt-4.md — 888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078 |
| Attempt-4 executor brief | .oracle/briefs/execution-batch-2-attempt-4-luna.md — aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9 |
| v2 finding, stale receipt | .oracle/findings/execution-batch-2-attempt-4-v2-luna.md — dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff; .oracle/receipts/execution-batch-2-attempt-4-v2-luna.md — 130e1e35883b16738718c46e13f6229b23a64184777790e5a755e791916ef831 |
| v2 final-seal gap receipt | .oracle/receipts/execution-batch-2-attempt-4-v2-final-seal-gap.md — 7a1d548d73808a317847f5ae25fe236fb4d93b646836f72fcefcc95efdf28299 |
| Correct raw final manifest | 70 captured files, 6213 bytes, SHA-256 7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e |
| Frozen tasklist | .oracle/tasklist.md — 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589 |
| Frozen North Star | .oracle/northstar.md — d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e |
| Frozen plan / goal / custody | 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1 / 2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864 / 94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0 |

The v2 finding's 70-file/6213-byte/7cd41d3d manifest identity is the correct
raw final identity. The v2 receipt's 65-file/5760-byte/70fc93c7 identity is
stale and must be described as superseded, not reproduced or treated as a
second valid manifest.

## North Star — canonical byte-for-byte block

<!-- NORTH_STAR_SHA256_BEGIN -->
# North Star — Arnold self-healing supervision

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
<!-- NORTH_STAR_SHA256_END -->

Verify the extracted bytes, including their final newline, equal
.oracle/northstar.md and hash to
d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e.

## Sole correction action

Independently inspect the preserved evidence root
/tmp/arnold-b2-attempt4-v2-luna-evidence.cLNWAe/ without changing it. Recompute
the canonical manifest exactly as the v2 final-seal gap receipt defines it:
include every regular capture except manifest.sha256, emit each SHA-256 with
its evidence-root-relative POSIX path, sort complete lines bytewise by relative
path, preserve the final newline, and hash the exact manifest bytes. Independently
run shasum -a 256 -c manifest.sha256 and count the checked files. Confirm and
report exactly 70 captured files, 6213 manifest bytes, and SHA-256
7cd41d3dd5e5e0c5a988e6f6205b4d34045e9cf7522b034e99103f0d182bfc9e. Report any
discrepancy honestly; do not repair or overwrite the evidence root.

The receipt must state that the earlier v2 receipt is stale only, that the v2
finding's final identity is corroborated, and that this correction adds no new
implementation or test evidence. Bind the manifest path, count, byte count,
algorithm, independent-check result, capture-root file inventory, and all
source/candidate/frozen identities above. Include exact read-only command
argv/body, cwd, UTC start/end, exits, separate stdout/stderr bytes and SHA-256,
and candidate pre/post porcelain and index proof.

## Required outputs and non-actions

Write only the v3 finding and receipt named above. They must be append-only and
must not alter either v2 artifact or the gap receipt. Explicitly record no
source/test/frozen/status/index/history/custody mutation, no test rerun, no
nested model, no review, no commit, and no Batch-3 action. Do not infer a batch
verdict from this receipt correction; a later gate must consume the corrected
receipt and a fresh seal.
