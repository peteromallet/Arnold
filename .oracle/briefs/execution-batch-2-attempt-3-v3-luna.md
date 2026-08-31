# Batch-2 attempt-3 v3 — Luna evidence-correction execution brief

## Narrow leaf boundary

This is a narrowly scoped Normal GPT-5.6 Luna/high **evidence-correction**
continuation. It is not a review, Oracle gate, verdict, or invitation to
change production/tests. Do not launch any nested model, delegation, OMP,
Megado, Megaplan, reviewer, fallback, Batch 3, or remote process. Do not edit
source or tests, commit, stage, push, merge, rewrite history, or modify frozen
documents/status/custody/goal/tasklist. Preserve all prior artifacts
immutably. Use only local evidence commands and create only the versioned
finding and receipt named below.

The operator may launch this brief once with the following exact command; this
brief's executor must not invoke that command or any launcher itself:

```bash
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-batch-2-attempt-3-v3-luna.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=1800
```

## Fixed bindings

Work only in `/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch
`megado-nbf-guard-0826`:

| Binding | Value |
|---|---|
| HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate parent | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate source/test diff | `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec` |
| Candidate diff byte count | `126804` bytes |
| Candidate production-only diff | `f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549` |
| Attempt-3 packet / triage receipt | `ff19d01688124ef3b77dba28ab24c28da71b395838c645a3a34f7b580c24c1e2` / `5d08b2b2f31a8a85f602c449311bd05a775711f298db963a8bc611f81abfab38` |
| Prior attempt-3 timeout receipt | `678e86f3a1f18e304507249b8175195374375da4ebd46610de30761b421ba3df` |
| Prior v2 brief | `5de88060bc2b2045ccf34ff86b08624ccc95e6f9ba909039706a31a7e8f12539` |
| Prior v2 finding / receipt | `7145641b049ec9d84efece8f35786e08abeaf80423f607be312e7f6d26b32e0f` / `58189132e6a5660a6812bffd3a020badb0a503a50858febd244ae73a0f12310b` |
| Frozen tasklist | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Frozen North Star | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Frozen plan / goal / custody | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` / `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |

The v2 artifact hashes above were independently measured from the current
immutable files and must be rechecked before the finding/receipt are sealed.
Do not substitute a digest from an earlier attempt.

## North Star — canonical byte-for-byte block

The block between markers, excluding marker lines and the fence, is the complete
`.oracle/northstar.md`, including its original final newline. Verify extracted
SHA-256 equals
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

<!-- NORTH_STAR_SHA256_BEGIN -->
```text
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
```
<!-- NORTH_STAR_SHA256_END -->

## Scope 1 — exact literal raw-symbol shell command

Run and capture the exact brief-mandated shell command below as literal shell
argv, with UTC start/end, exit status, separate stdout/stderr byte counts and
SHA-256. Do not replace it with a Python helper, specialized grep wrapper, or
human summary. An empty match is the expected success (exit 0 for the `if`
compound command); a match exits 1 and must be recorded.

```bash
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

This command is an evidence correction only. It does not authorize source or
test changes and does not substitute for the static authority checker.

## Scope 2 — correct command ordering and identity transcripts

The prior v2 receipt reported command 7 (`git diff --quiet`) as “paths differ.”
That interpretation is false: `git diff --quiet <base> -- <paths>` exits 0
when there is **no diff** for those paths, and exits 1 when a diff exists. The
v3 finding and receipt must correct this statement, preserve the raw prior
claim as historical evidence, and state the actual semantic meaning. Do not
rewrite or delete the v2 artifacts.

Re-emit the initial command outcomes for commands 07–10 from the prior v2
evidence in their literal order, retaining exact original exit codes, stream
sizes, stream SHA-256 values, and timestamps. Identify command 07 as the
`git diff --quiet` preservation check, command 08 as the three-file `shasum`,
command 09 as the authority checker, and command 10 as the forbidden-symbol
raw scan. Explicitly disclose that prior command 10 was not a literal shell
`rg` invocation if that is what its transcript shows; the exact literal shell
command in Scope 1 must now be freshly captured.

Capture the frozen identity transcript below exactly, with literal argv and
separate streams. Verify the candidate diff emits exactly `126804` bytes before
hashing and that its SHA is the bound `acb8...` value:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/main
git show -s --format='%H%n%P%n%T' 5da26ec5be4d13559948fe4256a114ad7626482b
git diff --binary --full-index 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests | shasum -a 256
git diff --name-status 5da26ec5be4d13559948fe4256a114ad7626482b -- arnold_pipelines scripts tests
git ls-files --others --exclude-standard -- arnold_pipelines scripts tests
```

Use an external evidence directory only; do not add transcripts to the repo.
Capture `git diff --check` only if needed to establish unchanged evidence, and
do not rerun expensive broad suites already validly sealed by v2.

## Scope 3 — immutable versioned outputs

Create only these new files, after all evidence is captured:

* `.oracle/findings/execution-batch-2-attempt-3-v3-luna.md`
* `.oracle/receipts/execution-batch-2-attempt-3-v3-luna.md`

Both must be labeled executor evidence, not review or Oracle judgment. Bind
candidate/HEAD/source/frozen identities, v2 finding/receipt full hashes, the
timeout receipt, exact commands and literal argv, initial 07–10 outcomes,
corrected `git diff --quiet` semantics, raw-shell `rg` transcript, complete
identity transcript, byte/hash/path status, and all external stream digests.
State explicitly that no source/test/frozen/history/status/index mutation,
review, nested model/delegation, commit, or Batch-3 action occurred. Do not
issue `PASS_BATCH_2` or `ACCEPTED_ISSUES`; this correction cannot make an Oracle
decision.
