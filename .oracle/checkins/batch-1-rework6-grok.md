PASS_BATCH_1

# Grok 4.6 Oracle verdict — NBF-01 / Batch 1 rework 6

**Verdict:** `PASS_BATCH_1`

- Oracle: Grok 4.6 (manager/validator only; no implementation)
- Date: 2026-08-30
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924` (verified)
- Candidate branch: `megado-nbf-guard-0826`
- HEAD (planning, not NBF-01 code): `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Merge-base with `origin/main`: `798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Settled plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Agent goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Attempt-6 packet SHA-256: `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83`
- Attempt-6 triage receipt: `88a0c2b76663cf63a32129296a74a610d01a4bedf66aef04dbaec570979bbcc8`
- Executor finding: `.oracle/findings/execution-nbf01-rework6-luna.md` (`a28a0ff726cccbc00806a44c7f8c7d305019491cf37656b6ad91769250806c44`)
- Executor receipt: `.oracle/receipts/execution-nbf01-rework6-luna.md` (`48d3988675ad1002000f193b915470391c83632bfc815fff2c35d8bd50a937e6`)
- Luna review brief: `.oracle/briefs/oracle-nbf01-rework6-luna-review.md` (`4d84369890661e68450a6ae3bff1ffb22681cd9c6a5b1824ce7d9e1dc83dae38`)
- Luna review: `.oracle/checkins/batch-1-rework6-luna.md` (`de278150f2245ce7330694470f5b474788aaf1e234c712a5099dfbda2aeef850`)
- Luna review receipt: `.oracle/receipts/oracle-nbf01-rework6-luna.md` (`ce5136fde4af45a8d64f372b733ae1868c4b718258177bff88e6f262527ca4ba`)
- Gate brief: `.oracle/briefs/oracle-nbf01-rework6-grok.md` (`2f9c8e074d4b9ae083ae110ff83bd646937eb57fc32175c586acb5a28dc15275`)
- Owned production diff SHA-256: `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`
- Attempt-5 production baseline (historical): `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`
- Isolated Oracle probe root: `/tmp/oracle-nbf01-rework6-grok-gate/`
- Isolated Luna review root: `/tmp/oracle-nbf01-rework6-luna-review/`
- This check-in: `.oracle/checkins/batch-1-rework6-grok.md`
- This decision receipt: `.oracle/receipts/oracle-nbf01-rework6-grok.md`

Do not commit, push, or begin Batch 2 from this Oracle turn. `[XHARD]` remains none. Batch 2 remains prohibited until an authorized later dispatch; this gate only unblocks that later authorized start.

## Gate and evidence identity

Exactly one independent GPT-5.6 Luna full review was commissioned at high
reasoning. No second reviewer, fan-out, helper review, tiebreaker, or Grok
self-review was commissioned. This turn is Oracle synthesis only.

Launcher:

```text
python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="codex:gpt-5.6-luna:high" \
  --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf01-rework6-luna-review.md \
  --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf \
  --timeout=3600 \
  --metadata-file=/tmp/oracle-nbf01-rework6-gate/luna_launch.meta.json
```

Resolved model `openai-codex/gpt-5.6-luna`, thinking `high`. Hub name
`luna-rework6-review`, pid `2846`. Launcher metadata:
`/tmp/oracle-nbf01-rework6-gate/luna_launch.meta.json` SHA-256
`21a58a4fb452ca293ec71b62c9147ae59426019d3d96b3a39137b2dddf16f7b0`.
File records `status=completed`, `exit_code=0`, `elapsed_seconds=1346.191`.
Hub start `2026-08-30T05:56:08Z`; launcher done in `1346.2s`; process exit 0.

Every bound identity listed in the gate brief was independently rehashed and
matched, including historical attempt-5/4 artifacts labeled historical. Owned
tracked-production diff independently reproduces
`ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`.
`tests/arnold_pipelines/megaplan/test_incident_ledger.py` is unchanged versus
`origin/main` (blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`). Scope
remains the five modified production files, new `incident/disposition.py`, and
the eight named new test modules. RW-CUSTODY remains MET.

Oracle independently reran focused `124 passed in 15.40s` (stdout SHA-256
`4af247d492a8d696b50ec5676c6da406718caee4f0dff24aa55385d321415dc8`) and legacy
`78 passed in 1.23s` (stdout SHA-256
`57c0c53f35c958bc21b56b3815fba4dd35c438a8fbb0e0db78cd2b3a72d4859c`). Named
three-module suite: `28 passed in 14.10s` (stdout SHA-256
`bc83eff88d9120124438c684700ad4dec1162f74fd9d943fedcffe10453f04e3`). Luna
independently reran focused `124 passed` (stdout SHA-256
`d02f8db1b55d2d556c5266f5a93039079ab7f2a35b8b929f314760b46ee8c2ea`) and legacy
modules `78 passed` (stdout SHA-256
`dbeeed5fc6eb2b714e0ecbae6f425a7cdf740c3205c49a08775adfdf7bbc3975`). Counts
remain observations, not targets. `py_compile` and `git diff --check` exit 0
with empty-stream SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Historical evidence remains historical and was not rewritten: start-gate 52→61,
unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`,
failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`,
attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`,
attempt-2 production digest `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`,
attempt-3 production digest `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`,
attempt-4 production digest `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`,
attempt-5 production digest `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`.
Current candidate digest `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`
is not an attempt-5 target.

Luna recommended `RECOMMEND_PASS_BATCH_1`. Oracle independently re-read the
named tests, `ObservedProcessDeath.__post_init__`, `DispatchOutcome` payload
family checks, and reproduced the six-kind/four-door matrix plus identity,
authority, and confirmation probes. The surviving attempt-5 named-proof hole
is closed.

## Hard gates

| Gate | Status |
| --- | --- |
| One fresh immutable attempt-6 Luna execution receipt/finding | **MET** |
| Exactly one fresh independent Luna full review at required paths | **MET** |
| Candidate/diff and independent test-transcript digests recorded | **MET** via Luna review plus Oracle rehash/rerun |
| North Star disposition, KISS/YAGNI stated by Luna and Grok | **MET** as statements |
| All frozen NBF-01 must criteria met with behavioral evidence | **MET** (C01/C40 remain `UNEVIDENCED` by explicit exclusion) |
| 52-vs-61 and `4aee815d…` treated as historical, not rewritten | **MET** |
| RW-CUSTODY unchanged | **MET** |

`PASS_BATCH_1` is available because C02/C13 are now named four-door proof, not
incidental missing-field `ValueError`s, and every other frozen must criterion
is MET or explicitly unevidenced-and-excluded.

## Criterion dispositions

Statuses: `MET` | `NOT_MET` | `UNEVIDENCED`. Oracle confirmation is against the
post-attempt-6 candidate, Luna's isolated `/tmp/oracle-nbf01-rework6-luna-review/`
transcripts, and Oracle's independent `/tmp/oracle-nbf01-rework6-grok-gate/` probes.

### NBF-01 acceptance criteria (tasklist)

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| C01 | Strict round-trip of scheduling / six outcome kinds | **UNEVIDENCED** | Attempt 6 correctly did not reopen C01-as-`PhaseResult.from_dict` overweight. |
| C02 | Invalid kind/state/payload combinations reject | **MET** | Named `test_dispatch_outcome_incompatible_payload_matrix` and `test_incompatible_matrix_rejects_at_public_terminal_append` now feed complete `legal.to_dict()` records and assert payload-family fragments. Independent Oracle probe `/tmp/oracle-nbf01-rework6-grok-gate/rw6_independent_probe.json` (`dc2fdfcc6703b2584b98b229057434de57ff026307111671da4bf5947d6dd55a`): all six kinds reject at ctor/`from_dict`/`validate_nbf_event`/public `append_disposition`/public `append_terminal_outcome` with intended families (`no_launch cannot carry`, `success cannot carry`, `ordinary failure cannot carry`, `provider exhaustion cannot carry`, `worker_disposition cannot carry`; scheduling kinds at terminal validation `invalid terminal outcome kind`). No incidental `missing DispatchOutcome fields`. Legal scheduling still hits `scheduling outcomes have no worker terminal event`. |
| C03 | `no_launch` cannot serialize with `launch_state=accepted` | **MET** | Constructor plus focused transcript. |
| C04 | `worker_disposition` required context | **MET** | Constructor plus named context tests. |
| C05 | Worker disposition cannot carry provider-exhaustion or no-launch state | **MET** | Constructor and `validate_nbf_event`. |
| C06 | Maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)` | **MET** | Classify/append mapping tests. |
| C07 | Mapping validates exactly one already-committed matching disposition | **MET** as sequential CAS | Locked identical-replay. Concurrent distinct-ID proof is C09. |
| C08 | Never coerced into ordinary failure | **MET** | Named coercion test. |
| C09 | Duplicate linkage idempotent; conflicting linkage/kinds reject | **MET** | Distinct-ID two-process terminal linkage retained. |
| C10 | Persisted accepted launch required | **MET** | Marker-bound terminal writer retained. Structurally complete but marker-mismatched worker identity independently rejects `terminal outcome accepted-launch marker mismatch: worker_identity` at public `append_terminal_outcome`. |
| C11 | Disposition breaks consecutiveness without degradation | **MET** as named proof | Keyed reducer plus non-latest named tests. |
| C12 | `no_launch` produces no worker terminal/fingerprint/provider/streak | **MET** | Terminal writer rejects `no_launch` / `unresolved_launch`. |
| C13 | Worker / observed-death / non-worker reject incomplete or fabricated identities | **MET** as named proof | Named worker identity matrix now covers `None`, bare string, wrong type, incomplete mapping, non-positive PID, malformed host/boot, and wrong schema version at ctor/`from_dict`/`validate_nbf_event`/public disposition/public terminal. Named observed/non-worker test covers missing/fabricated subject/cause/killer/victim/lifecycle and wrong version at all four applicable doors. Independent probe matches. Packet “mismatched typed worker identity” is wrong types / non-positive PID (named); a complete but different `{host,pid,boot_id}` is C10 marker mismatch, not a schema-incomplete identity. |
| C14 | OOM requires positive cgroup evidence; unknown death remains unknown | **MET** | Legal positive OOM and unknown-death append paths retained; Oracle probe accepted both. |
| C15 | TERM and KILL ladder IDs are distinct | **MET** | Named test remains. |
| C16 | Semantic fingerprint excludes volatile liveness and logical/family IDs | **MET** | Named provider/fingerprint test. |
| C17 | Route-liveness digest absent from fingerprint and provider-failure key | **MET** | Same named test. |
| C18 | Same projection key + fingerprint contend for one reservation | **MET** | Real two-OS-process `fcntl.flock` race. |
| C19 | Only allowlisted reason-specific producers may mint changes | **MET** | Independent Oracle probe: forged `from_dict` rejected `missing fields: ['_source_handles']`; `validate_nbf_event` / `_append_nbf` / `_append_nbf_locked` rejected handle error; public append rejected; `reserve()` of unpersisted forged id rejected; valid reader appended and consumed once. |
| C20 | Producer, evidence, subject, version, before/after, provider-key binding validated | **MET** | `_validate_producer_binding` plus named producer tests remain. |
| C21 | Forged unequal content IDs or provider-failure-key transitions reject | **MET** | Coherent recomputation of snapshots, keys, content IDs, evidence digest, and event ID rejected at every caller-visible NBF door and did not project. |
| C22 | Valid changed-precondition consumed at most once | **MET** | Valid reader appends, consumes once; second consume rejected `changed precondition already consumed`. |
| C23 | `provider_recovery_verified` may authorize one linked same-route child | **MET** | Lease-bound passed probe plus named recovery matrix. |
| C24 | Other allowlisted change resets/rekeys only when canonical before/after keys differ | **MET** as reducer | Keyed rekey tests pass. |
| C25 | Ordinary two-process reservation contention yields one winner | **MET** | Same evidence as C18. |
| C26 | `provider_route_child_reserved` is one record and contains no child receipt-ID input | **MET** | Shape retained. |
| C27 | Receipt identity derives after append and reproduces byte-for-byte | **MET** | Real composite fresh replay retained. |
| C28 | Torn or failed writes cannot expose partial transitions | **MET** | Pre-append `_emit_locked` and post-append receipt-boundary crash/reopen proofs present. |
| C29 | Accepted terminal projects fingerprint state before reservation closure | **MET** | Reducer order retained. |
| C30 | Matching accepted `provider_exhausted` increments keyed streak | **MET** | Matching-stream increment retained. |
| C31 | Nonmatching accepted `provider_exhausted` rekeys at one | **MET** | Named rekey-at-one test. |
| C32 | Accepted worker success resets applicable streak and active key | **MET** as named proof | Required non-latest success test present. |
| C33 | Intervening ordinary failure or worker disposition breaks consecutiveness | **MET** as named proof | Required ordinary-failure named test present. |
| C34 | Probe results and recovery preserve matching streak | **MET** | Canonical probe/recovery named tests present. |
| C35 | Scheduling, no-launch, unresolved, time, liveness refresh do not mutate provider streak | **MET** | No provider-terminal reducer branch. |
| C36 | Reconciliation permits only the three frozen resolutions | **MET** | Not reopened. |
| C37 | Recovered worker disposition links one existing canonical disposition | **MET** | Not reopened. |
| C38 | Blind release, conflicting reconciliation, and accepted-launch release as no-launch reject | **MET** | Not reopened. |
| C39 | Durable two-scan state survives restart; TTL, scan separation, identity equality | **MET** | Independent Oracle probe: wrong `second_evidence={"alive": False}` rejected `confirmation evidence identity mismatch`; omitted helper evidence `TypeError`; omitted ledger digest rejected; matching consume accepted; second consume rejected. Restart/replacement/expiry/one-consumer tests remain. |
| C40 | Ledger lock, append, schema, projection-version, and cache failures fail closed | **UNEVIDENCED** | Attempt 6 correctly did not expand cache-mismatch. |
| C41 | Disposition CLI schema validation, acknowledgements, and exit codes match §4.21 | **MET** | Luna independent real subprocesses: statuses `[0, 2, 2, 3, 4, 5, 5, 5]` (stdout SHA-256 `b2d687aa21c9f18f0d9d497cbdcdd6dc93469ad25c11cdf97ecbd03af9b3ac14`, manifest SHA-256 `9804b5a2f9fae2d3b872f6870cc1fda59af551833c1c299420f1776f6cdd50b0`). Oracle independently reproduced status 2 malformed (`45c31321…`), 2 schema (`2525d332bcb419a8…`), 4 (`d66b73aa…`), 5 missing (`ba1b0851…`), 5 expired (`4a94dd27…`). Status 0 is one JSON ack and does not signal. |

### Batch 1 checkpoint

| ID | Checkpoint | Status |
| --- | --- | --- |
| CP01 | Every NBF-01 focused test passes | **MET** as pytest gate (Oracle: `124 passed in 15.40s`; Luna: `124 passed`). Count is observation. |
| CP02 | Schema fields and legal transitions match owned §§4.4–4.13, §4.16, §§4.19–4.21 | **MET** — C02 named matrix and C13 completeness now present. |
| CP03 | `DispatchOutcome.kind=worker_disposition` is lossless and maps exactly once | **MET** |
| CP04 | One incident-ledger authority | **MET** for journal count / lock door. |
| CP05 | Accepted exhausted worker outcomes are the only increment inputs | **MET** |
| CP06 | `provider_recovery_verified` remains single-use retry authorization | **MET** |
| CP07 | Success resets; different-key rekeys at one; ordinary/disposition break consecutiveness | **MET** as named keyed proof. |
| CP08 | Composite transition and child reservation remain one append with post-commit receipt | **MET** |
| CP09 | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition are mechanically distinct | **MET** for type/state and illegal payload named matrix. |
| CP10 | No second journal, store, prepare/commit, scheduler, rotator, or policy owner | **MET** |
| CP11 | Crash, contention, replay, torn-write, linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass | **MET** | Real races/crashes/TTL exist and C02/C13 named four-door proof is now complete. |

### Rework tasks

| ID | Status | Evidence |
| --- | --- | --- |
| RW6-01 | **MET** | Complete six-kind/four-door named tests plus independent probes; one necessary production mapping guard. |
| RW5-01 | **MET** | Public producer, `validate_nbf_event`, `_append_nbf`, `_append_nbf_locked`, projection, and `reserve()` reject the prior coherent forgery. Valid reader still appends and consumes once. |
| RW5-02 | **MET** after RW6-01 | Named tests now feed correctly shaped `DispatchOutcome` records through public `append_terminal_outcome` for every kind, with intended error families. |
| RW5-03 | **MET** | Wrong and omitted `second_evidence`/`second_evidence_digest` reject; matching consume-once remains. |
| RW4-01 | **MET** after RW5-01 | Historical attempt-4 hole closed at the canonical NBF append door. |
| RW4-02 | **MET** after RW6-01 | Same named four-door completeness as RW5-02/RW6-01. |
| RW4-03 | **MET** | Required non-latest / recovery / lease names remain green. |
| RW4-04 | **MET** | Distinct-ID terminal race and post-append composite crash/reopen proofs remain. |
| RW4-05 | **MET** after RW5-03 | CLI 0/2/3/4/5 independently proved. Confirmation evidence-digest mismatch/omission remains named. |
| RW4-06 | **MET** | Attempt-6 finding/receipt bind HEAD, source, production diff, per-file inventory, dedicated gate-command transcripts. |
| RW6-GATE | **MET** | This Oracle gate returns `PASS_BATCH_1`. |
| RW-CUSTODY | **MET** | Custody SHA `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` unchanged. |

### A3 dispositions

| A3 item | Status | Hole closed? |
| --- | --- | --- |
| A3-01 | **MET** | Fully populated terminal without persisted accepted marker rejects. |
| A3-02 | **MET** after RW6-01 | Named matrix is now a complete four-door six-kind proof. |
| A3-03 | **MET** | Coherent recomputed forgery rejected at `validate_nbf_event` and `_append_nbf`; not projected; `reserve()` of the unpersisted id rejected. |
| A3-04 | **MET** | Required non-latest named tests are present. |
| A3-05 | **MET** | Canonical probe binding and negative matrix are present. |
| A3-06 | **MET** | Distinct terminal race and post-append crash are present. |
| A3-07 | **MET** | CLI complete; confirmation evidence-digest named matrix remains. |
| A3-08 | **MET** | Attempt-6 executor inventory/stream completeness is present. |
| A3-09 | **MET** | Unofficial `reserve_provider_route_child_with_receipt` remains absent. |

## Independent probe results

### RW6-01 / C02 complete matrix

Independent production-behavior probe
`/tmp/oracle-nbf01-rework6-grok-gate/rw6_independent_probe.json`
(`dc2fdfcc6703b2584b98b229057434de57ff026307111671da4bf5947d6dd55a`)
rejects all six incompatible kinds at construction, `from_dict` of complete
`to_dict()` records, `validate_nbf_event`, public `append_disposition`, and
public `append_terminal_outcome`. `six_kind_all_payload=true`. Legal OOM,
unknown-death, non-worker, worker-disposition, success public terminal, and
scheduling-no-terminal paths behave as required.

Attempt-5 named-proof hole independently reconstructed
(`/tmp/oracle-nbf01-rework6-grok-gate/attempt5-gap-reconstruction.json`,
SHA-256 `5907d4f7978b43674c99e6b2879f94542502618c250bf2a87ec7d1c7b657b53e`):
incomplete dictionaries still reject `missing DispatchOutcome fields` for all
six kinds and never reach payload-family checks. Luna reconstructed the
attempt-5 schema SHA-256 `5c150cdc5a55769a209f216ea7954831f76f8aae64606bf36a14a003312a27b1`;
that copy accepts a fabricated non-empty victim string. Current named tests
against that old schema failed as required (`attempt5-current-tests-00` exit 1).
The exact historical untracked attempt-5 test blob
`45b23313a67229de5d3bbb1c896ab7729b4d09da` is absent from this checkout's Git
object database; that absence is recorded, not silently claimed. The packet's
incomplete-dict / any-`ValueError` hole is independently proven without it.

### RW6-01 / C13 identity

Named worker identity matrix covers missing, fabricated non-mapping, bare
string, incomplete mapping, non-positive PID, malformed host/boot types, and
wrong schema version at every applicable door. Named observed/non-worker
matrix covers missing/fabricated subject, cause, killer, victim identity
evidence (including the fabricated string that required the production
correction), empty mapping, empty/wrong-type lifecycle identity, worker
subject/cause, and wrong schema version at ctor/`from_dict`/`validate_nbf_event`/
public `append_disposition`. Independent Oracle probe `observed_all_match=true`.

The only production delta versus attempt 5 is:

```diff
+        if not isinstance(self.victim_identity_evidence, dict):
+            raise ValueError("victim identity evidence must be a typed object")
```

That guard is required: attempt-5 truthiness accepted `"fabricated-victim"`;
attempt 6 rejects `victim identity evidence must be a typed object`; empty
mappings still reject `victim identity evidence is required`. No other
production seam changed. Ledger/phase_result/disposition hashes match the
attempt-5 inventory.

### RW5-01 authority closure

Oracle rebuilt a valid `produce_source_revision_changed` event, mutated
before/after snapshots and both provider keys, recomputed content IDs,
evidence digest, and event ID, then probed every required door.

| Door | Result |
| --- | --- |
| `ChangedPrecondition.from_dict(forged)` | rejected `missing fields: ['_source_handles']` |
| `validate_nbf_event(forged)` | rejected `requires a typed authoritative source handle` |
| `IncidentLedger._append_nbf(forged)` | rejected same handle error |
| `_append_nbf_locked(forged)` | rejected same handle error |
| public `append_changed_precondition(forged)` | rejected missing-handle error |
| `reserve(..., changed_precondition_event_id=forged["event_id"])` before persist | rejected `missing or already consumed` |
| valid reader append / consume once / second consume | accepted / accepted / rejected |

No second journal, signing service, or generic producer bypass was added.

### RW5-03 confirmation evidence equality

Independent probe in the same JSON:

- wrong `second_evidence={"alive": False}` rejects `confirmation evidence identity mismatch`
- omitted helper `second_evidence` raises `TypeError`
- omitted ledger `second_evidence_digest=None` rejects
- matching evidence consumes once; second consume rejects

## Luna comparison

Luna recommended `RECOMMEND_PASS_BATCH_1` with the same C02/C13 MET call, the
same C01/C40 UNEVIDENCED exclusions, the same RW5-01/RW5-03 closures, and the
same one-line production delta. Oracle independently reproduced the six-kind
four-door matrix, identity matrices, authority doors, confirmation equality,
focused 124/legacy 78, and production-diff digest. No material contradiction.
Residual `_IncidentEventJournal._emit_locked` journal-primitive exposure
remains outside the frozen RW5-01 door set and is not reopened.

## Broad-suite relevance classification

Attempt 6 and this gate did not rerun `pytest -q tests/arnold_pipelines/megaplan`.
The authoritative pre-existing collection failures remain:

1. `test_cli_check_validator.py` → `arnold.agent.costing.model_resource_capabilities`
2. `test_key_pool_codex.py` → `tools.environments.singularity`

Both modules are absent on the candidate and absent at `origin/main`.
Classification: **PRE_EXISTING_OUT_OF_SCOPE_BLOCKER**. This is context, not a
waiver or implementation issue.

## North Star and KISS/YAGNI

- **One door per invariant:** MET for Batch-1 primitive scope. One
  `_IncidentEventJournal`, one sequence-sidecar flock, one NBF append
  authority, one terminal writer, one disposition helper, one reason-specific
  producer boundary. Admission, live model membership, physical launch, and
  real signal-site doors remain deferred later-batch scope, not duplicated here.
- **Deaths speak:** MET as owned foundation. Worker, observed-death, and
  non-worker records are typed; OOM requires positive cgroup evidence;
  TERM/KILL IDs differ; CLI records and does not signal. Repository-wide
  signal wiring remains later scope.
- **Models admitted, not assumed:** UNEVIDENCED and correctly deferred.
- **Fixes ship on main:** UNEVIDENCED for this dirty uncommitted candidate;
  delivery is a later guarded checkpoint.
- **Anti-patterns:** durable confirmation equality/TTL avoids single-scan
  truth; typed dispositions replace anonymous exits; accepted-launch markers
  provide positive proof; identical-fingerprint redispatch requires a changed
  precondition.
- **KISS/YAGNI:** MET. No second store, signing framework, generic producer
  escape hatch, scheduler, rotator, family lease, or speculative admission
  machinery. The sole attempt-6 production correction is the necessary typed
  victim-evidence guard. Test-count growth from 123 to 124 is an observation.

## Preservation proof

Independently confirmed intact: one `_IncidentEventJournal` + sequence-sidecar
flock; NBF writes still enter `_locked` / `_append_nbf_locked`; C03–C12,
C14–C18, C19–C21, C22–C39, C41; CP04 journal count; CP05 increment rule;
CP06–CP10; RW-CUSTODY; A3-01 and A3-03 through A3-09; route-child wrapper
absence. Frozen tasklist, North Star, custody, status
(`bbcf8bc7f5a0688e136f16f6e63dc80240eb85856be7dc4d1d829b860f585dfc`), agent
goal, and historical receipts were not mutated by this Oracle turn. No
commit, stage, push, merge, rebase, reset, clean, or Batch 2 action occurred.

## Next action

No blocking issue remains inside the frozen Batch-1 contract. The smallest
authorized next action is a separately dispatched Batch 2 start under the
frozen tasklist, not a seventh rework packet and not a main merge.
