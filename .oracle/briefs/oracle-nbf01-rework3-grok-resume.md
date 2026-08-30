# Oracle resume brief — NBF-01 Batch 1 rework 3

## Gate handoff and immutable bindings

Resume the NBF-01 Batch 1 rework-3 Oracle gate as Grok 4.6. Read the completed
Luna executor artifacts and the relevant current source/tests, then
independently synthesize the final verdict. Write:

- `.oracle/checkins/batch-1-rework3-grok.md`
- `.oracle/receipts/oracle-nbf01-rework3-grok.md`

Return exactly `PASS_BATCH_1` or `ACCEPTED_ISSUES`. If issues remain, identify
the smallest concrete attempt-4 triage next action. The prior Grok gate timed
out only while writing, after its independent checks had confirmed Luna's
coherent-forgery blocker.

Bind the decision to candidate repository
`/Users/peteromalley/Documents/Arnold-oracle-nbf`, branch
`megado-nbf-guard-0826`, source `origin/main@798c50619204010ed3f4297fbb57988fe9381924`,
frozen tasklist SHA-256
`9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`, and North
Star SHA-256
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

Reviewed artifact identities:

- gate brief: `5b062d0ded7552ce01bb7b4a7231a349419102a219c967c9a05cfbf46f2fdc01`
- Luna executor receipt: `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f`
- production diff: `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`
- Luna review check-in: `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd`
- Luna review receipt: `ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425`

Exactly one independent Luna review is already satisfied. Do **not** commission
any additional reviewer, fan-out, or second review. Do not edit production or
tests; do not commit, stage, push, merge, start Batch 2, mutate the frozen
tasklist, or rewrite historical evidence. This is an Oracle decision only.

## North Star — Arnold self-healing supervision

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

## Oracle decision requirements

Read the full attempt-3 packet and completed Luna artifacts, verify source/diff
and test-evidence binding, and record the final verdict in the two Oracle-owned
files above. Keep historical 52→61, unreproducible `4aee815d…`, and prior
attempt observations labeled as historical; do not rewrite them.
