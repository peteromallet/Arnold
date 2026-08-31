# Batch-2 attempt-4 post-custody Luna review — authority/checker/integration lens

## Review identity and hard boundary

Conduct a fresh, independent, read-only GPT-5.6 Luna/high review in a new
session with no reused reviewer or executor context. The original attempt-4
review artifacts are invalid and excluded because the original worktree drifted
from HEAD `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` to external commit
`819ce9da03694fb25d2c0b6613030e9aa8f1722e`, including frozen-goal drift. Do
not treat those outputs as evidence.

This is review evidence only. Read the reconciled tree; do not modify source,
tests, frozen files, status, history, custody, index, or prior artifacts. Do not
commit, stage, push, merge, launch/delegate/nest any model or reviewer, start
Batch 3, or implement fixes. Review budget is 3600 seconds.

Write exactly these fresh paths and no old cwd-bound names:

- `.oracle/checkins/batch-2-attempt-4-post-custody-authority.md`
- `.oracle/receipts/oracle-batch-2-attempt-4-post-custody-authority.md`

Place captures only in `.oracle/evidence/batch-2-attempt-4-post-custody-authority/`.
The check-in is a source-based review; the receipt records model/session proof,
literal commands, timestamps, exits, streams and hashes, pre/post identities,
and output hashes. Do not issue PASS/ACCEPTED or any other batch verdict.

## Immutable bindings

| Binding | SHA / identity |
|---|---|
| Target / branch / HEAD | `/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4` / `reconcile/nbf-attempt4-2297` / `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source/base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate commit | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate full / production diff | `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` / `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` |
| Packet / executor brief | `.oracle/rework/batch-2-attempt-4.md` — `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078`; `.oracle/briefs/execution-batch-2-attempt-4-luna.md` — `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9` |
| Executor finding / receipt | `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda` / `4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502` |
| v2 correction finding / receipt | `dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff` / `130e1e35883b16738718c46e13f6229b23a64184777790e5a755e791916ef831` |
| v3 correction finding / receipt | `5c87675363343bddbbaf43e5c7520cf3a6012ae65863151dddbdfcf398571b29` / `2e462d5532577fb348443461bf4369cdec512af0b4f535eefdfee73f6b5ace9e` |
| Sealed manifest | `.oracle/evidence/batch-2-attempt-4-sealed.md` — `5238ec05d2f19e798c0fa3e8dc7fbe75876505393ef61411b22fa82a86211e5b` |
| Frozen tasklist / North Star | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` / `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Base goal / status / plan / custody | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` / `9f4c6a0794a87d18aaac3e49109baa7ed792d86571483913625ebc1507e362af` / `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Custody / review policy | `a0ecba2b2c7076bb992fe8169698e895d3e83a49733d0d74c8331dbd1e7dddae` / `1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc` |

Rehash all bindings. The target is the good base plus the candidate patch and
allowlisted valid Oracle artifacts; commit 819 evolution and all drifted
attempt-4 review outputs are excluded.

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

Verify marked bytes including final newline equal the canonical North Star and
SHA `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

## Full Batch-2 criteria and authority/integration lens

Review every frozen Batch-2 criterion and all four roots, concentrating on
single-authority enforcement, checker completeness, and integration without
scope expansion:

1. **R3-NATIVE-001 — native authority.** The selected backend/runtime/model
construction seam, not a resolver-only shortcut, must positively prove and
recompute exact content, generation, model identity, registry/family,
route/provider, age, digest, and `constructable is True`. Unknown/expired,
stale, negative, forged, ambiguous, or mismatched proofs refuse typedly before
reservation, WBC, client, process, RPC, or launch; a valid proof constructs
once. Verify the authority boundary and adversarial tests.

2. **R3-TERM-002 — physical typed terminal authority.** Native, OMP, managed,
normalization/dispatch, and phase doors must preserve complete admission,
dispatch, worker, timing, receipt, fingerprint, phase, spec, route, and worker
identities for typed success, ordinary failure, provider exhaustion, and worker
disposition. Mismatches reject; one canonical terminal append, typed-death
terminalization, full-context append/link-failure unresolved hold,
`PhaseResult.dispatch_outcome`, failure-shaped non-success, and no provider
degradation coercion are required. Use the physical doors and real fixtures.

3. **R3-LIFE-003 — persisted lifecycle authority.** Globally validate the
complete legal persisted transition matrix `not_started → entered → accepted →
closed` and idempotent replay. Reject closed-first, accepted-before-entered,
entered-after-accepted, stale not-started, conflicting duplicates, and mixed
door histories. Reopen must validate all history and receipt-bound physical
evidence; it must not choose strongest markers or selectively release a held
reservation. Preserve commit-before-projection, no-launch, at-most-once,
replay, and durable ambiguous holds.

4. **R3-AUTH-004 — checker/WBC integration.** Flag-on OMP forwards the canonical
WBC adapter; `wbc_dispatch=None` constructs it or refuses before controlled
entry/reservation and never raw-launches. The contextual checker must catch
qualified/import/module/assignment/call aliases, reversed and multiline
absent-WBC, aliased process/raw launch, nested/double admission, ordering, and
chain preflight/launch regardless of enclosing symbol. Every frozen category
has a negative fixture and independent raw-symbol scan. Keep checker scope
bounded; it is not runtime authority or a general linter.

Preserve valid RTB, CHILD, OMP, and SCHED roots. Reject overreach into T8,
provider policy, generic six-kind/every-door work, Batch-3 crash semantics,
signal-site wiring, extra scheduler/journal, or speculative probes. Treat the
four babysitter failures as baseline only with clean-checkpoint and source
evidence. Assess KISS/YAGNI and North Star alignment.

## Required review record

Use read-only source inspection and only targeted non-mutating probes. Record
literal argv/body, cwd, UTC timestamps, exits, separate stream byte counts and
SHA-256, model/session proof, pre/post porcelain, branch/HEAD, frozen hashes,
candidate full/production diff, and index state. Rehash all outputs and fresh
captures. Explicitly exclude the custody-drift review artifacts. Return only
the uniquely named check-in and receipt; do not alter files or issue a batch
verdict.
