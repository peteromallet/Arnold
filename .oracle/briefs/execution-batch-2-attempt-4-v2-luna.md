# Batch-2 attempt-4 v2 — Luna evidence-only correction brief

## Purpose and hard boundary

This is a narrow, evidence-only correction pass for the attempt-4 executor
record. It is not implementation, review, Oracle adjudication, or a new
rework. Correct only the three evidence gaps identified by the authoritative
gap receipt. Do not edit source, tests, frozen documents, status, history,
custody, tasklist, North Star, plan, goal, or the git index. Do not commit,
stage, push, merge, reset, rewrite prior artifacts, start Batch 3, invoke any
nested model or reviewer, or run any test other than the one exact clean-copy
baseline command below. Use a fresh evidence directory and never overwrite
attempt-4 evidence or artifacts.

Create only these new versioned executor artifacts after completing the captures:

- .oracle/findings/execution-batch-2-attempt-4-v2-luna.md
- .oracle/receipts/execution-batch-2-attempt-4-v2-luna.md

These are evidence corrections, not a verdict. The executor must not change
production/test content and must not issue PASS_BATCH_2 or ACCEPTED_ISSUES.

The operator launch metadata, which the executor must not run, is exactly:

    PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-batch-2-attempt-4-v2-luna.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=1800

## Immutable bindings

Rehash every binding before and after the correction. The candidate remains the
existing dirty tree and must be unchanged.

| Binding | Identity |
|---|---|
| Repository / branch | /Users/peteromalley/Documents/Arnold-oracle-nbf / megado-nbf-guard-0826 |
| Current HEAD | 2297fb330cdb375b4e5bd048f0d5c37d0e06db30 |
| Source/base | origin/main@798c50619204010ed3f4297fbb57988fe9381924 |
| Candidate implementation | 5da26ec5be4d13559948fe4256a114ad7626482b |
| Candidate parent / tree | 19deab5bb407273e7e82d40a66fc06d17af93ad4 / e3d0376482154c4f95d2ec5809d630c4a0c32e69 |
| Attempt-4 full source/test diff | 67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163 |
| Attempt-4 production-only diff | 009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32 |
| Attempt-4 packet | .oracle/rework/batch-2-attempt-4.md — 888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078 |
| Attempt-4 executor brief | .oracle/briefs/execution-batch-2-attempt-4-luna.md — aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9 |
| Attempt-4 finding / receipt | .oracle/findings/execution-batch-2-attempt-4-luna.md — ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda; .oracle/receipts/execution-batch-2-attempt-4-luna.md — 4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502 |
| Evidence-gap receipt | .oracle/receipts/execution-batch-2-attempt-4-evidence-gap.md — fff19e2b4f45ce7a3238cb4848fcd95373a08475c60a9a88b4a5a442bc12c760 |
| Frozen tasklist | .oracle/tasklist.md — 9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589 |
| Frozen North Star | .oracle/northstar.md — d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e |
| Frozen plan / goal / custody | 0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1 / 2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864 / 94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0 |

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

The extracted bytes, including the final newline, must equal
.oracle/northstar.md byte-for-byte and hash to
d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e.

## Correction 1 — literal raw-symbol shell capture

Use the terminal execution tool, not a specialized repository-search
abstraction, to run exactly this multiline shell body from the repository root:

    if rg -n \
      'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
      arnold_pipelines/megaplan/workers/_impl.py \
      arnold_pipelines/megaplan/workers/omp.py \
      arnold_pipelines/megaplan/cloud/babysitter/launch.py
    then
      exit 1
    fi

Capture the literal argv and script bytes, cwd, UTC start/end, exit code,
separate stdout/stderr bytes and SHA-256, pre/post porcelain, and changed-path
hashes in the fresh evidence directory. Expected result is exit 0 with empty
stdout and stderr, each SHA-256
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
Record the outer shell exit 0 and empty output as the expected no-forbidden-
symbols pass; do not reinterpret it as a mismatch.

## Correction 2 — isolated clean-source baseline

Create a new explicitly named temporary archive directory without touching the
candidate. Capture the literal command, argv/body, cwd, UTC times, exit, and
separate streams for each step. Use this exact construction shape, with a fresh
nonexistent path recorded in the receipt:

    CLEAN_ROOT="$(mktemp -d /tmp/arnold-b2-attempt4-v2-clean.XXXXXX)" && git archive 19deab5bb407273e7e82d40a66fc06d17af93ad4 | tar -x -C "$CLEAN_ROOT"

Inside that archive, run exactly this one two-module pytest command and no other
test command:

    cd "$CLEAN_ROOT" && PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py

The expected baseline result is exit 1 with exactly `12 passed, 4 failed` and
these four failure identities, all unchanged from the clean source checkpoint:

1. tests/cloud/test_babysitter_routing.py::test_babysitter_routing_defaults_to_legacy_deepseek
2. tests/cloud/test_babysitter_routing.py::test_legacy_managed_spec_keeps_hermes_controller
3. tests/cloud/test_babysitter_goal.py::test_renderer_requires_single_flash_orchestrator_contract
4. tests/cloud/test_babysitter_goal.py::test_renderer_cli_mentions_single_flash_contract

Record the complete pytest stdout/stderr and hashes. The historical accepted
clean reproduction stdout SHA is
f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c; compare and
report any difference rather than silently substituting it.

Then capture exactly these parent-preservation commands from the candidate
repository root, with literal argv and independent streams:

    git diff --quiet 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- arnold_pipelines/megaplan/cloud/babysitter/routing.py skills/babysitter/scripts/render_babysitter_goal.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py
    shasum -a 256 arnold_pipelines/megaplan/cloud/babysitter/routing.py tests/cloud/test_babysitter_routing.py tests/cloud/test_babysitter_goal.py
    test -z "$(git ls-tree -r --name-only 19deab5bb407273e7e82d40a66fc06d17af93ad4 -- skills/babysitter/scripts/render_babysitter_goal.py)"
    test -z "$(git ls-tree -r --name-only HEAD -- skills/babysitter/scripts/render_babysitter_goal.py)"

Expected results are parent diff exit 0, exact unchanged-path hashes matching
the recorded receipt, and both renderer-absence checks exit 0 with empty output.

## Correction 3 — reproducible evidence manifest

Preserve every capture from Corrections 1 and 2 plus pre/post identity and
porcelain records under one fresh external evidence directory. Create a sorted
manifest using a documented canonical algorithm: for every captured file except
the manifest itself, emit a shasum -a 256 line with its evidence-root-relative
POSIX path; sort those lines bytewise by path; write the resulting lines with a
final newline; hash that exact manifest. Do not include an output that is being
hashed, the manifest itself, or any unrecorded absolute path. Record the
manifest path, algorithm, file count, byte count, and SHA-256 in both v2
artifacts. Recompute the digest independently before declaring the correction
complete.

## Final custody and deliverables

Prove candidate HEAD, branch, source base, full source/test diff, production
diff, frozen tasklist, North Star, plan, goal, custody, index, and tracked path
inventory are unchanged before and after. Record every command's exact result,
streams, timestamps, and digest. The v2 finding and receipt must bind the three
new captures, manifest construction and SHA, all original attempt-4 identities,
and the evidence-gap receipt. State that no source/test/frozen/status/index
mutation, nested model, review, commit, or Batch-3 action occurred. Do not
rewrite or delete the original attempt-4 finding, receipt, or gap receipt.
