# Batch-2 attempt-4 post-custody Luna review — evidence/authenticity lens

## Review identity and hard boundary

This is a fresh, independent, read-only GPT-5.6 Luna/high review of the
reconciled attempt-4 candidate. Use a new session with no prior reviewer or
executor context. The original attempt-4 evidence/authenticity, runtime, and
authority review outputs are invalid and excluded because custody drift
advanced the original worktree from HEAD `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`
to external commit `819ce9da03694fb25d2c0b6613030e9aa8f1722e` and changed the
frozen goal. Do not consume those outputs as review evidence.

Review only. Do not edit source, tests, frozen documents, status, history,
custody, the index, or any existing artifact. Do not commit, stage, push,
merge, launch another model, delegate, nest a reviewer, start Batch 3, or
issue an implementation change. Inspect the reconciled tree and bound
artifacts directly with read-only tools. Review budget is 3600 seconds.

Write only these fresh unique outputs, using their exact paths:

- `.oracle/checkins/batch-2-attempt-4-post-custody-evidence.md`
- `.oracle/receipts/oracle-batch-2-attempt-4-post-custody-evidence.md`

Capture/refer to review evidence only under the unique path
`.oracle/evidence/batch-2-attempt-4-post-custody-evidence/`. The check-in must
give a complete source-based review; the receipt must record model proof,
session identity, commands, timestamps, exits, stream hashes, candidate
pre/post identities, and every output hash. Do not emit a batch verdict;
these are Luna review evidence for the single later Oracle gate.

## Immutable bindings

| Binding | SHA / identity |
|---|---|
| Repository / branch | `/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4` / `reconcile/nbf-attempt4-2297` |
| Reconciled HEAD | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate implementation commit | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate full source/test diff | `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` |
| Candidate production diff | `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` |
| Attempt-4 packet | `.oracle/rework/batch-2-attempt-4.md` — `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078` |
| Attempt-4 executor brief | `.oracle/briefs/execution-batch-2-attempt-4-luna.md` — `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9` |
| Attempt-4 finding / receipt | `.oracle/findings/execution-batch-2-attempt-4-luna.md` — `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda`; `.oracle/receipts/execution-batch-2-attempt-4-luna.md` — `4fe99da6fde53c45e1ffcbbc1cca732f22e1f00c9735c321633b93dce8cb3502` |
| Attempt-4 v2/v3 evidence correction | v2 finding `dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff`; v2 receipt `130e1e35883b16738718c46e13f6229b23a64184777790e5a755e791916ef831`; v3 finding `5c87675363343bddbbaf43e5c7520cf3a6012ae65863151dddbdfcf398571b29`; v3 receipt `2e462d5532577fb348443461bf4369cdec512af0b4f535eefdfee73f6b5ace9e` |
| Correct sealed manifest | `.oracle/evidence/batch-2-attempt-4-sealed.md` — `5238ec05d2f19e798c0fa3e8dc7fbe75876505393ef61411b22fa82a86211e5b` |
| Frozen tasklist | `.oracle/tasklist.md` — `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Frozen North Star | `.oracle/northstar.md` — `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Base frozen goal / status | `.oracle/agent_goal.md` — `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`; `.oracle/status.md` — `9f4c6a0794a87d18aaac3e49109baa7ed792d86571483913625ebc1507e362af` |
| Frozen plan / custody | `.oracle/plan.md` — `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`; `.oracle/custody.md` — `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Custody reconciliation receipt | `.oracle/receipts/custody-reconciliation-819ce9.md` — `a0ecba2b2c7076bb992fe8169698e895d3e83a49733d0d74c8331dbd1e7dddae` |
| Review-policy receipt | `.oracle/receipts/review-policy-override-multi-luna-single-sol.md` — `1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc` |

The reconciled target was made from the good base and contains the candidate
source/test patch only in the production/test roots plus the explicitly
allowlisted Oracle evidence. Commit 819 and its evolution/status/goal drift
are not in this target. Rehash every consumed file and record full hashes.

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

The bytes between the markers, including the final newline, must equal the
canonical file and hash to `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

## Full Batch-2 criteria and evidence/authenticity lens

Assess all four rework roots and all frozen Batch-2 acceptance criteria,
especially whether evidence is authentic, complete, recomputed at the actual
authority boundary, and bound to the candidate rather than merely narrated.

1. **R3-NATIVE-001 — authoritative native proof.** In
`cloud/worker_dispatch.py`, `workers/_impl.py`, and the native runtime/model
construction seam, proof must come from the selected backend/runtime/model
construction seam. Recompute and bind exact content, generation, model
identity, registry/family, route/provider, observation age, and digest; require
`proof.constructable is True`. Unknown/expired models, stale, absent,
ambiguous, negative, forged, self-consistent, or mismatched proof must refuse
typedly before reservation, WBC, client, process, RPC, or launch construction;
valid proof constructs exactly once. Check tests and evidence for actual
authority, not a resolver-only or callable-presence claim.

2. **R3-TERM-002 — physical-door typed terminal transport.** In native,
OMP, managed babysitter, normalization/dispatch, and phase transport doors,
operation-specific typed success, ordinary failure, provider exhaustion, and
worker disposition must retain all admission, dispatch, worker, timing,
receipt, fingerprint, phase, spec, route, and worker identities. Mismatch
rejects and never overwrites. A canonical terminal event is recorded once;
typed death, append/link failure, unresolved hold, `PhaseResult.dispatch_outcome`,
failure-shaped-result non-success, and no provider-degradation coercion must
hold. Verify real native/OMP/managed doors, not a generic lambda fixture.

3. **R3-LIFE-003 — global persisted transition reconciliation.** The locked
ledger door must enforce the complete persisted legal transition matrix
`not_started → entered → accepted → closed` and idempotent replay globally.
Reject closed-first, accepted-before-entered, entered-after-accepted, stale
not-started, conflicting duplicate, and mixed-door histories. Reopen validates
complete history plus receipt-bound physical evidence; it cannot choose a
strongest marker or selectively release a reservation while an accepted marker
remains. Preserve commit-before-projection, no-launch, replay, at-most-once,
and durable-ambiguous-hold behavior.

4. **R3-AUTH-004 — physical WBC closure and contextual checker.** Flag-on OMP
must forward the canonical WBC adapter. `wbc_dispatch=None` constructs it or
refuses before controlled entry/reservation and never reaches raw launch. The
checker must inspect every call in configured door files independent of
enclosing function spelling, classifying qualified/import/module/assignment/
call aliases, truthy/reversed/multiline absent-WBC, aliased process/raw launch,
nested/double admission, WBC ordering, and chain preflight/launch with
contextual diagnostics. Each frozen negative category needs a fixture and an
independent raw-symbol scan. Do not turn this into a general linter or runtime
authority.

Preserve valid RTB/canonical admission, CHILD/child authorization, OMP/no-WBC,
and SCHED/wait-ownership dispositions. Do not overreach into T8/provider
policy, generic six-kind/every-door expansion, Batch-3 crash semantics,
signal-site wiring, a new scheduler/journal, or speculative network probes.
Treat the four unchanged babysitter failures as baseline only when source and
clean-checkpoint evidence supports that conclusion. Check KISS/YAGNI and the
North Star’s one-door, typed-death, admitted-model, and main-line principles.

## Required review record

Use the evidence/authenticity lens to independently inspect source, tests,
sealed manifest, prior valid artifacts, and the custody receipt. Run only
targeted non-mutating probes needed to verify claims. For every command record
literal argv/body, cwd, UTC start/end, exit, separate stdout/stderr byte counts
and SHA-256, and pre/post `git status --porcelain=v1 -uall`, HEAD, branch,
frozen-file hashes, candidate diff hashes, and index state. Rehash both outputs
and the fresh capture files. Explicitly state which original custody-drift
outputs were excluded. Do not broaden the work or make edits; return one
evidence check-in and one receipt at the unique paths above.
