# Batch-2 attempt-4 final post-plan Luna review — runtime/terminal/lifecycle

## Fresh review boundary

Conduct a fresh, independent, read-only GPT-5.6 Luna/high review in a new
session of the reconciled Gate4 candidate. Focus on runtime behavior at native,
OMP, managed, terminal, and persisted lifecycle doors. The plan is now present
and authenticated. All pre-isolation and first post-custody review outputs
listed below are quarantined and cannot be used as evidence.

Do not edit source/tests/frozen documents/status/history/custody/index or prior
artifacts. Do not commit, stage, push, merge, delegate, invoke or nest another
model/reviewer, start Batch 3, or implement fixes. Write only:

- `.oracle/checkins/batch-2-attempt-4-post-plan-runtime.md`
- `.oracle/receipts/oracle-batch-2-attempt-4-post-plan-runtime.md`

Capture only under `.oracle/evidence/batch-2-attempt-4-post-plan-runtime/`,
with an approximate total budget of 64 MiB. Review time budget is 3600 seconds.
Record literal read-only command argv/body, cwd, UTC start/end, exits, separate
stream byte counts/SHA-256, model/session proof, pre/post status/HEAD/branch,
frozen hashes, candidate diff hashes, index, and output hashes. No batch verdict.

## Immutable bindings

| Binding | Identity |
|---|---|
| Repository / branch / HEAD | `/Users/peteromalley/Documents/Arnold-oracle-nbf-gate4` / `reconcile/nbf-attempt4-2297` / `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| Source base / candidate | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` / `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate full / production diff | `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163` / `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32` |
| Packet / executor brief | `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078` / `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9` |
| Executor / v2 / v3 evidence | `ac65e5d896a7745330e4aaf9594fd074fc7087adbb7b50f4f90e2df978341cda` / `dbcd4a264c42b1cdca952dbb58bee5ad7d1ccbbcc89e1b6ec5eb4895a7a054ff` / `5c87675363343bddbbaf43e5c7520cf3a6012ae65863151dddbdfcf398571b29` |
| Sealed manifest | `5238ec05d2f19e798c0fa3e8dc7fbe75876505393ef61411b22fa82a86211e5b` |
| Tasklist / North Star / plan | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` / `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` / `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| Goal / status / custody | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` / `9f4c6a0794a87d18aaac3e49109baa7ed792d86571483913625ebc1507e362af` / `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Custody original / supplement / policy | `a0ecba2b2c7076bb992fe8169698e895d3e83a49733d0d74c8331dbd1e7dddae` / `e7f4f6d442eb9bfa0d8e9ebd61bac0be763f422c660b36dbd03763922dacf1cb` / `1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc` |

## Quarantine ledger

Exclude pre-isolation checkins/receipts: evidence `378f1c4ed0e7218c4cd05adfe04473592ba78d678cf677e2796d5616c9d71833`/`01faad4d7e1ac1bf9e777e1cba36136a8ef2c877bcb5268b38e02b23f4cb4a6c`, authority `d5055c1802297650d67e9e637fb929fa6fd0bab4bfde666cdee12c53ebcf122c`/`0110c72cbfd5e728e28b6619b34cb27a720c73a86e02de29fa1fe531f3f9486f`, and interrupted runtime `16ccf35286f3b2cf604022ec97a7d37ea07e30dff7f029c8afdbbd57a14bf08` (no receipt). Exclude first post-custody plan-absent outputs: evidence `78f1f8b401224e3928259d4761788be030a56890ebb0f8840bb5d66839291f51`/`bc2551be63d580a8ff9fa5a8b1d8a88c4f43eb7fde20b05a19071047f774e26f`, authority `e55d21098930a946576c6663031b1fefe2caba801ccd9b42984aba2af055a7eb`/`04878932bc796d03a8ad9efd2079f1af05f88b3ee1bda21770b33040b4254b5e`, and interrupted runtime `34637402e8a7645b88b7d68bd67bad80314b2f5c0e23e8ab0007e6641094cb96` (no receipt). Do not use any of them for a gate conclusion.

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

## Full Batch-2 criteria

Review all four roots. **R3-NATIVE-001:** positive construction-seam proof
recomputes content, generation, model, registry/family, route/provider, age,
and digest with `constructable is True`; every unknown, stale, forged, negative,
ambiguous, or mismatched proof refuses before reservation or physical work, and
valid proof constructs once. **R3-TERM-002:** native/OMP/managed physical doors
transport typed success, ordinary failure, provider exhaustion, and worker
disposition while preserving every admission, dispatch, timing, receipt,
fingerprint, phase, spec, route, and worker identity; mismatch rejects, terminal
append is once-only, typed death and append/link failure retain full context, and
phase consumers receive `dispatch_outcome`. **R3-LIFE-003:** persisted history
globally obeys `not_started → entered → accepted → closed`, rejects all illegal
first/backward/mixed/conflicting histories, and reopen validates complete bound
evidence without strongest-marker selection; preserve no-effect, replay,
at-most-once, commit-before-projection, and ambiguous-hold behavior.
**R3-AUTH-004:** canonical WBC is forwarded; absent WBC constructs or refuses
before entry; configured-door checker coverage is independent of enclosing
symbol and catches all qualified/aliased/reversed/multiline process, raw-launch,
WBC, nested/double-admission, ordering, and chain categories, with fixtures and
raw-symbol scan. Preserve RTB/CHILD/OMP/SCHED; reject T8, provider-policy,
generic six-kind/every-door, Batch-3, signal-site, extra scheduler/journal, and
speculative network scope. Assess baseline babysitter failures with clean proof,
KISS/YAGNI, and North Star alignment.

## Runtime lens

Exercise only bounded, targeted, non-mutating probes at the actual native,
OMP, managed, terminal, phase, ledger, and reopen doors. Compare behavior to
source and the sealed manifest; specifically detect tuple metadata loss,
dispatcher-identity fallback, accepted-first persistence, and lifecycle
strongest-marker restoration. Record true source defects separately from test
coverage gaps and quarantined evidence.
