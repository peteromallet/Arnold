# Independent Luna Review A — Evidence and Authenticity

**Review-only check-in.** This artifact is an independent GPT-5.6 Luna/high evidence and authenticity review. It is not a Sol review, Oracle gate, acceptance token, or Batch-2 verdict. No source, test, frozen artifact, status, index, history, commit, stage, push, merge, model launch, delegation, or fan-out was performed.

## Review invocation and custody

- Reviewer: `openai-codex/gpt-5.6-luna`; thinking: `high`.
- Required launcher invocation shape recorded literally (not re-run by this review):
  `PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-batch-2-attempt-3-luna-evidence.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600`
- Authorized v3 executor capture: wrapper start `2026-08-30T18:55:56.847840000Z`, end `2026-08-30T19:05:30.957165000Z`, launcher PID `23486`, wrapper exit `0`, model exit `0`, model duration `573.7s`.
- Resolved executor model: `openai-codex/gpt-5.6-luna`; launcher stderr records `thinking=high` and cwd `/Users/peteromalley/Documents/Arnold-oracle-nbf`.
- This review's read-only verification shell: PID `34370`, observed `2026-08-30T19:20:32.013954000Z` through `2026-08-30T19:24:26.253527000Z`, commands exited `0` unless explicitly noted below, cwd `/Users/peteromalley/Documents/Arnold-oracle-nbf`.
- Wrapper stream hashes, rehashed: `meta.txt` 374 bytes `5b852fb79d1da03f03d7be5c1a172e5dc26f9dae1ab3759e6189b1358e5d3f21`; `stdout.txt` 1272 bytes `9c32622901d4575b1d333399289aed12e99f01327fc258a01e716cb57f6ee597`; `stderr.txt` 463 bytes `0618f08c37d054823cb3c2702e93ae91be4f82a0b91d58f2e3dac3d834496613`.

## Candidate and frozen-byte rehash

All required frozen hashes rehashed from the current tree and matched the supplied bindings:

| Artifact / identity | Recomputed SHA-256 or value |
|---|---|
| Branch | `megado-nbf-guard-0826` |
| Current `HEAD` | `2297fb330cdb375b4e5bd048f0d5c37d0e06db30` |
| `origin/main` | `798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate checkpoint used as diff base | `5da26ec5be4d13559948fe4256a114ad7626482b` |
| Candidate checkpoint parent | `19deab5bb407273e7e82d40a66fc06d17af93ad4` |
| Candidate checkpoint tree | `e3d0376482154c4f95d2ec5809d630c4a0c32e69` |
| Current `HEAD` immediate parent/tree | `5f172e3588e740bacd6692ca9e4cc50ae01f6a6b` / `85d20103923d7d4f8c2c70869a95283a196d9249` |
| Source/test diff, 126804 bytes | `acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec` |
| Production-only diff, 84905 bytes | `f636e53dfdf83ab7bac8eeff80243822ce8b4bef43fbb445ce6713555c122549` |
| Diff statistics | 18 files, 1567 insertions, 75 deletions |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Sealed manifest `.oracle/evidence/batch-2-attempt-3-sealed.md` | `2c60512f34311883849d1530af4c5b719cab7bb29434087985905c36b2573cbf` |
| Current review brief | `1f8bfecaadc32b72c14f7681c88f04e28513d5fa36f5fbea51fa1ab3d1f78fb0` |

The current path-hash command was re-executed over all 18 listed source/test paths; every value matched the sealed capture. The 18 paths are the nine production paths plus the nine test/helper paths named in the sealed evidence. The v2 JSON records' embedded path hashes and stdout/stderr byte/hash pairs were independently parsed: zero embedded stream mismatches, and all 12 numbered records had equal pre/post porcelain. The v3 and v2 lexical manifests also recomputed exactly using sorted `shasum -a 256` lines with `./` relative paths:

- v3 root: 56 files, digest `ea42d7db641b06399ab0d51754b40f3fc77cf154a987981221447a2414cdd893`.
- v2 root: 16 files, digest `3a5731511d27d75c598820596c54cf8332c482874b241770ea64ef24daeadf3a`.
- R3 root: 9 files, digest `8405ad04406ba6c6a0caeb8e7d7a988e6a972c6fc2151c2088bde04693e34024`.

`/tmp/...` and `/private/tmp/...` resolve to the same evidence roots on this host.

## Historical provenance corrections

The immutable prior hashes rehashed successfully:

- v2 brief `5de88060bc2b2045ccf34ff86b08624ccc95e6f9ba909039706a31a7e8f12539`;
- v2 finding `7145641b049ec9d84efece8f35786e08abeaf80423f607be312e7f6d26b32e0f`;
- v2 receipt `58189132e6a5660a6812bffd3a020badb0a503a50858febd244ae73a0f12310b`;
- v3 finding `c216fc39fcdec21cf81f8a3bb43656b7dca5ef949a050a85ac1a81b0523569ee`;
- v3 receipt `cca7987c9f23eab5ec6c2a4cf80ceb1af84fd1d5e2503bc20421ef2685cb0bcf`;
- attempt-3 packet `.oracle/rework/batch-2-attempt-3.md` `ff19d01688124ef3b77dba28ab24c28da71b395838c645a3a34f7b580c24c1e2`;
- triage receipt `5d08b2b2f31a8a85f602c449311bd05a775711f298db963a8bc611f81abfab38`;
- timeout receipt `678e86f3a1f18e304507249b8175195374375da4ebd46610de30761b421ba3df`.

The v3 correction is authentic about the earlier defects, but the historical v2 receipt remains internally mislabelled: its table calls frozen record 07 a preservation check, while the literal `07.json` command is the three-file `shasum`; it similarly shifts records 08–10. The v3 finding explicitly corrects this and preserves the original records rather than rewriting them. The earlier v2 `git diff --quiet` interpretation was also false: exit `0` means the selected paths were unchanged from the specified parent. These are correctly disclosed, not silently converted into passes.

A separate accuracy issue remains in mutable `.oracle/status.md`: line 4 states current HEAD `5f172e...`, while the actual current HEAD and sealed candidate are `2297fb...`. Its current SHA is `9f4c6a0794a87d18aaac3e49109baa7ed792d86571483913625ebc1507e362af`. Therefore any claim that a current CLI status is bound to this candidate is not usable without a fresh status capture.

## Preserved passed evidence

The v2 numbered records are cryptographically bound to the 18 candidate paths through before/after path hashes and have zero embedded stream mismatches. The preserved results are:

| Preserved area | Evidence | Review disposition |
|---|---|---|
| RTB/source-runtime | v2 records 01 and 05: 56 and 254 passed | MET as preserved test evidence |
| CHILD/linked transition | v2 records 02/03 and R3 lifecycle coverage | MET as preserved test evidence |
| OMP catalog and rejection fixtures | v2 records 02/03/05; live resolver code reviewed | MET for recorded fixture coverage; no fresh live CLI capture |
| SCHED/T7 | v2 record 04 and record 05; cooldown loop has bounded injected timing | MET as preserved test evidence |

These labels do not waive the remaining physical-door and candidate-byte-binding gaps below.

## Four roots

### `R3-NATIVE-001` — **NOT_MET**

The focused transcript is authentic (`4 passed`, stdout SHA `44091516c6f7d278c9900d796163d45f95d1ad1819370ffeeaf887bc704f2e38`); its tests cover forged resolver content and digest mismatch. The implementation still accepts a semantically negative proof when its digest is self-consistent:

- `worker_dispatch.py:528-530` requires truthy `proof`, not `proof["constructable"] is True`.
- `worker_dispatch.py:535-536` rejects only `proof is False`, so `{"constructable": False}` passes.
- `worker_dispatch.py:587-588` requires nonempty generation fields but imposes no freshness/age validation on `observed_at`.
- `worker_dispatch.py:665-679` treats the selected construction seam as authority; `_production_worker_dispatch` also accepts `options.get("native_construction_seam")` at `_impl.py:7458-7460`.

A no-write direct probe built a correctly recomputed native proof with `constructable=False` and an old `1900-01-01` observation. `_validate_native_liveness(..., authoritative=bad)` returned `ACCEPTED` rather than rejecting it. The existing stale test changes `observed_at` and the digest together only to exercise digest disagreement; it does not prove semantic-negative or stale-self-consistent rejection. Thus content/generation/digest recomputation is present, but the positive-present constructability and freshness contract is not met.

### `R3-TERM-002` — **NOT_MET**

The focused transcript is authentic (`5 passed`, stdout SHA `a86fbc1eaf8fe3346837ab279229e9eb1b6170e862c47dae08b324a37c72100c`), but the physical transport does not reject receipt substitution:

- `worker_dispatch.py:754-758` replaces a `DispatchOutcome`'s receipt, fingerprint, route, and lifecycle identity with the admission receipt rather than comparing and rejecting mismatches.
- The mapping branch at `worker_dispatch.py:763-766` does the same.
- A no-write direct probe supplied `receipt-FORGED` and fingerprint `bbbb...`; the normalized result carried the real receipt and `aaaa...`, silently converting the mismatch into an apparent success.
- The ledger's direct append door does compare reservation context (`ledger.py:698-741`), but normalization occurs before that check and masks the caller's mismatched identity.

The R3 “physical door” tests are not actual native/OMP/managed door calls: `test_worker_dispatch_spy.py:94-109` creates a generic receipt, injects a gate that returns it, and calls `dispatch_with_admission` with a lambda. They establish generic category construction, not lossless transport through `_production_worker_dispatch`, `_run_omp_with_admission`, and `_admit_managed_launch`. The typed category schema is strong, and failure-shaped `WorkerResult` rejection is covered, but identity loss/replacement and physical-door authenticity prevent this root from passing.

### `R3-LIFE-003` — **NOT_MET**

The focused transcript is authentic (`5 passed`, stdout SHA `5c9258a0de83f38243aa16ddbdf4932629810a56e692fb8852a52f3a6f665024`), and it proves selected reconciliation contradictions, append-before-projection, idempotent no-launch replay, and identical retry suppression for the tested normal sequences. It does not prove the required global contradiction invariant:

- `ControlledFinalLaunch.__init__` selects the strongest marker in the order `closed`, `accepted`, `entered`, `not_started` (`controlled_final_launch.py:42-64`) without rejecting contradictory combinations.
- `ControlledFinalLaunch._persist` enforces only the in-memory predecessor (`controlled_final_launch.py:74-80`).
- `IncidentLedger.append_controlled_adapter_state` validates reservation binding and duplicate accepted markers but does not require an `entered` predecessor for `accepted` or an `accepted` predecessor for `closed` (`ledger.py:675-683`).
- `validate_nbf_event` validates the state vocabulary and accepted payload shape but no global transition matrix (`schema.py:1186-1202`).

Consequently an out-of-order or mixed persisted marker set can be silently classified by strongest-state selection rather than rejected as an accepted/entered contradiction. The normal-path tests cannot establish global persisted-state contradiction detection. Commit-before-projection and at-most-once behavior are partially evidenced, but this explicit root contract is not met.

### `R3-AUTH-004` — **UNEVIDENCED** (static implementation appears MET)

The focused transcript is authentic (`5 passed`, stdout SHA `0407c81f58a87403f115aa0196e1c68d7be7a22d330f09eabf4c946a853e91ff`), the broad checker suite is `13 passed` (stdout SHA `489cd4744986b1a46608752c592c91f6f46125cfc871ea7ba364743cd32906aa`), and the checker command returned `ok: true` with stdout SHA `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2`. The literal shell raw-symbol gate also has exit `0`, empty stdout/stderr, and command-text SHA `75b76d539959b07133a151c9f59776f8cdf5a76e182af7bea58d386ff25807c4`. The AST tests directly cover qualified/import/module/assignment/call aliases, aliased process launch, reversed multiline no-WBC delegation, WBC-before-admission, and nested/double admission diagnostics.

The label is UNEVIDENCED for the strict authenticity contract because the nine R3 JSON records record argv, timestamps, and streams but no cwd or per-command candidate path hashes. The later v3 path-hash capture proves the final bytes, not cryptographically that each earlier R3 command ran against those same bytes. The wrapper cwd is recorded, so this is a binding omission rather than evidence of a wrong cwd. The static source/checker result itself appears MET for the listed categories; the evidence package does not meet the requested independent candidate-byte binding standard.

## Full frozen contract status

| Criterion | Status | Direct evidence / reason |
|---|---|---|
| 1. One canonical admission authority and all pre-launch identities/proofs | **NOT_MET** | Native proof accepts self-consistent `constructable=False` and stale observations; see `R3-NATIVE-001`. |
| 2. T7 cooldown typed retry-wait, bounded/injectable, no breaker effect | **MET** | Candidate-path-bound v2 records 04/05 and preserved scheduling evidence; no new contradiction found. |
| 3. Global lifecycle and at-most-once closure | **NOT_MET** | No global persisted transition matrix; strongest-marker selection masks contradictions; see `R3-LIFE-003`. |
| 4. Native, direct/nested OMP, managed, chain, no-WBC one-owner doors | **UNEVIDENCED** | Static checker evidence is strong, but actual physical-door transport is not exercised by the R3 generic spy tests; explicit Codex managed route has no supplied native construction seam. |
| 5. All six payload kinds through every physical door with identity rejection | **UNEVIDENCED** | Typed generic transport tests pass, but they inject a common gate/closure rather than exercising every production door; receipt mismatch is normalized rather than rejected. |
| 6. Provider catalog/prefix/family/live membership/ox-alpha/streak/digest semantics | **UNEVIDENCED** | Static/catalog fixtures and resolver code are preserved; no captured live `omp models --json` command binds exact live membership to this candidate. |
| 7. Death killer/signal/elapsed, typed disposition, crash/contention/replay safety | **MET** | Candidate-path-bound v2 broad suite includes disposition, terminal, reservation, changed-precondition, and replay tests; no authenticity mismatch found in those records. This is test evidence, not an exhaustive production process-death proof. |
| 8. NBF-03 exact result, clean baseline, restored tests, scans, compile, diff/path/manifests, CLI status, no T8, KISS/YAGNI | **NOT_MET** | Frozen focused command 06 is `59 passed, 4 failed`; its four failures are disclosed baseline failures, not passes. Mutable status claims stale HEAD `5f172...`; historical command-order and `git diff --quiet` claims required correction. |

## Authenticity conclusion

The candidate, frozen hashes, diff bytes, path hashes, wrapper streams, evidence-root manifests, v2 finding/receipt, v3 finding/receipt, packet, triage receipt, and timeout receipt all rehash to their supplied values. The v3 executor correction is materially more truthful than v2 and correctly preserves the known command-order and `git diff --quiet` defects.

That integrity result does **not** turn the implementation into a pass. The strongest direct source probes find an accepted semantically-negative/stale native proof and silent receipt-identity substitution; lifecycle validation lacks global contradiction rejection. The R3 focused evidence is stream-authentic but not fully candidate-byte-bound because it lacks per-command cwd and path hashes. No Sol judgment is issued here.
