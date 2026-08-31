# Batch-2 attempt-4 post-custody Luna review — runtime/terminal/lifecycle lens

## Review identity and hard boundary

This is a fresh, independent, read-only GPT-5.6 Luna/high review of the
reconciled attempt-4 candidate, with a new session and no prior reviewer or
executor context. Original attempt-4 review outputs are invalid and excluded:
custody drift moved the original worktree from HEAD
`2297fb330cdb375b4e5bd048f0d5c37d0e06db30` to external commit
`819ce9da03694fb25d2c0b6613030e9aa8f1722e` and changed the frozen goal. Do not
use those evidence records.

Review only, read-only. Do not edit source/tests/frozen documents/status/
history/custody/index or existing artifacts; do not commit, stage, push, merge,
launch/delegate/nest another model or reviewer, start Batch 3, or implement a
fix. Inspect this reconciled tree directly. Review budget is 3600 seconds.

Write only:

- `.oracle/checkins/batch-2-attempt-4-post-custody-runtime.md`
- `.oracle/receipts/oracle-batch-2-attempt-4-post-custody-runtime.md`

Use only the unique capture root
`.oracle/evidence/batch-2-attempt-4-post-custody-runtime/`. Record model/session
proof, complete command metadata, streams/hashes, pre/post candidate identity,
and output hashes. This review must not issue a batch verdict.

## Immutable bindings

| Binding | SHA / identity |
|---|---|
| Repository / branch | `/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4` / `reconcile/nbf-attempt4-2297` |
| Reconciled HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate commit / full diff / production diff | `5da26ec5be4d13559948fe4256a114ad7626482b` / `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` / `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` |
| Attempt-4 packet | `.oracle/rework/batch-2-attempt-4.md` — `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078` |
| Attempt-4 execution brief | `.oracle/briefs/execution-batch-2-attempt-4-luna.md` — `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9` |
| Attempt-4 finding / receipt | `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda` / `4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502` |
| Attempt-4 v2/v3 evidence | `dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff` / `130e1e35883b16738718c46e13f6229b23a64184777790e5a755e791916ef831`; `5c87675363343bddbbaf43e5c7520cf3a6012ae65863151dddbdfcf398571b29` / `2e462d5532577fb348443461bf4369cdec512af0b4f535eefdfee73f6b5ace9e` |
| Sealed manifest | `.oracle/evidence/batch-2-attempt-4-sealed.md` — `5238ec05d2f19e798c0fa3e8dc7fbe75876505393ef61411b22fa82a86211e5b` |
| Frozen tasklist / North Star | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` / `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Base goal / status / plan / custody | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` / `9f4c6a0794a87d18aaac3e49109baa7ed792d86571483913625ebc1507e362af` / `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Custody / review policy receipts | `a0ecba2b2c7076bb992fe8169698e895d3e83a49733d0d74c8331dbd1e7dddae` / `1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc` |

Rehash all consumed artifacts. This target excludes commit 819’s evolution and
drifted goal/status and contains the reconciled candidate patch only.

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

Verify the marked bytes including final newline equal `.oracle/northstar.md` and
SHA `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

## Full Batch-2 criteria and runtime lens

Review all four roots and the complete frozen Batch-2 contract, concentrating on
actual runtime behavior at physical doors, typed identity preservation, and
persisted lifecycle legality:

1. **R3-NATIVE-001.** Native admission must obtain a positive proof from the
selected backend/runtime/model construction seam, recomputing exact content,
generation, model identity, registry/family, route/provider, age, and digest,
with `constructable is True`. Unknown, expired, stale, negative, forged,
ambiguous, or mismatched proof refuses typedly before reservation/WBC/client/
process/RPC/launch; valid construction occurs exactly once. Inspect the real
`worker_dispatch.py` and `_impl.py` seams and focused tests.

2. **R3-TERM-002.** Native, OMP, managed, normalization/dispatch, and phase
doors must transport typed success, ordinary failure, provider exhaustion, and
worker disposition without overwriting admission, dispatch, worker, timing,
receipt, fingerprint, phase, spec, route, or worker identities. Canonical
terminal append is exactly once; typed death, append/link failure with a full
context unresolved hold, `PhaseResult.dispatch_outcome`, forged mismatch,
failure-shaped non-success, and no degradation coercion all work. Test real
doors rather than generic fixtures.

3. **R3-LIFE-003.** The locked persisted ledger enforces globally legal
`not_started → entered → accepted → closed` transitions and idempotent replay.
Reject closed-first, accepted-before-entered, entered-after-accepted, stale
not-started, conflicts, and mixed histories. Reopen validates complete history
and receipt-bound physical evidence, not a strongest marker or selective early
ID; preserve commit-before-projection, no-launch, at-most-once, replay, and
durable ambiguous holds.

4. **R3-AUTH-004.** Flag-on OMP forwards the canonical WBC adapter;
`wbc_dispatch=None` constructs it or refuses before controlled entry/reservation
and never raw-launches. Contextual checker coverage must catch qualified/import/
module/assignment/call aliases, reversed/multiline absent-WBC, process/raw
launch aliases, nested/double admission, ordering, and chain preflight/launch
regardless of enclosing name. Every frozen negative category needs a fixture
and raw-symbol scan; do not make a general linter.

Preserve RTB, CHILD, OMP, and SCHED passed roots. Do not widen into T8,
provider policy, generic six-kind/every-door expansion, Batch-3 crash semantics,
signal-site wiring, new journals/schedulers, or speculative network probes.
Classify the four babysitter failures as baseline only with source and clean
checkpoint proof. Judge KISS/YAGNI and every North Star principle.

## Required review record

Use targeted read-only source inspection and runtime probes only. Record
literal command argv/body, cwd, UTC start/end, exit, separate stream bytes and
SHA-256, model/session proof, and candidate/frozen/index/status before and
after. Rehash every output and capture under the unique root. Explicitly mark
the original custody-drift outputs excluded. Return only the new check-in and
receipt; do not modify the repository or issue a batch verdict.
