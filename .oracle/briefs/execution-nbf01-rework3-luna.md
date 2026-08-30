# Executor brief — NBF-01 Batch 1 rework 3

## Authority and immutable bindings

This is a Normal/Luna implementation and validation handoff. Implement the
attempt-3 packet at `.oracle/rework/batch-1-attempt-3.md` in strict serial order:

`RW3-01 → RW3-02 → RW3-05 → RW3-03 → RW3-04 → RW3-06`

Use one writer only. Inspect the current dirty tree and build on it, preserving
accepted primitives and user changes. Use `apply_patch` for edits. Run every
packet test plus the frozen focused and legacy suites, `py_compile`,
`git diff --check`, and the strongest obvious in-scope behavioral tests. Publish
the immutable executor finding and receipt requested by the packet with full
argv, cwd, exit status, stdout, stderr, and stdout/stderr SHA-256 digests.

The candidate is `/Users/peteromalley/Documents/Arnold-oracle-nbf` on
`megado-nbf-guard-0826`. Bind all evidence to:

- source: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- attempt-3 packet SHA-256: `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`
- attempt-3 triage receipt SHA-256: `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b`
- attempt-2 tracked-production diff starting identity:
  `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`

Do not commit, stage, push, merge, rebase, start Batch 2, mutate the frozen
tasklist, rewrite historical evidence, or issue an Oracle verdict. Do not edit
`.oracle/northstar.md`; the complete authoritative text follows verbatim.

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

## Deliverables

After implementation and validation, write only the two attempt-3 evidence files
owned by the packet:

- `.oracle/findings/execution-nbf01-rework3-luna.md`
- `.oracle/receipts/execution-nbf01-rework3-luna.md`

Label them executor evidence, not Oracle review. Include candidate HEAD/source,
tasklist/North Star/packet identities, exact command transcripts and digests,
and the final production-diff digest. Report completion or a concrete blocker;
never silently stall.
