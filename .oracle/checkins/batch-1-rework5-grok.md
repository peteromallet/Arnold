ACCEPTED_ISSUES

# Grok 4.6 Oracle verdict — NBF-01 / Batch 1 rework 5

**Verdict:** `ACCEPTED_ISSUES`

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
- Attempt-5 packet SHA-256: `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7`
- Attempt-5 triage receipt: `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a`
- Executor finding: `.oracle/findings/execution-nbf01-rework5-luna.md` (`8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197`)
- Executor receipt: `.oracle/receipts/execution-nbf01-rework5-luna.md` (`4acbb75c4bc9526265bf14438d194288bdf4aaf79cc63525f729830c6f93f160`)
- Luna review brief: `.oracle/briefs/oracle-nbf01-rework5-luna-review.md` (`3407bead7ac04e582248349ae23c40d3f197fc4e87951c7140efe80c1fa79380`)
- Luna review: `.oracle/checkins/batch-1-rework5-luna.md` (`670dbde42ab483ac36e08f2d1222d83b80a42248c6036d47cbeb77459649a8a6`)
- Luna review receipt: `.oracle/receipts/oracle-nbf01-rework5-luna.md` (`4d96b1922cb6dca3b79c5d414092cb0407f49c32c95236e54fb08530994cc143`)
- Gate brief: `.oracle/briefs/oracle-nbf01-rework5-grok.md` (`c4f82720a787b9594e5a68663546ec081db7776a8089c795817a1e5b915d9428`)
- Owned production diff SHA-256: `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`
- Historical attempt-4 production diff: `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`
- Isolated Oracle probe root: `/tmp/oracle-nbf01-rework5-grok/`
- Isolated Luna review root: `/tmp/oracle-nbf01-rework5-luna-review/`
- This check-in: `.oracle/checkins/batch-1-rework5-grok.md`
- This decision receipt: `.oracle/receipts/oracle-nbf01-rework5-grok.md`

Do not commit, push, or begin Batch 2 on this candidate. `[XHARD]` remains none.

## Gate and evidence identity

Exactly one independent GPT-5.6 Luna full review was commissioned at high
reasoning. No second reviewer, fan-out, helper review, or Grok self-review was
commissioned. This turn is Oracle synthesis only.

Launcher:

```text
python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="codex:gpt-5.6-luna:high" \
  --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf01-rework5-luna-review.md \
  --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf \
  --timeout=3600 \
  --metadata-file=/tmp/oracle-nbf01-rework5-gate/luna_launch.meta.json
```

Resolved model `openai-codex/gpt-5.6-luna`, thinking `high`. Start
`2026-08-30T04:29:47Z` (launcher spawn), end `2026-08-30T04:52:20Z` (launcher
done), elapsed `1353.018s`, launcher exit `0`. Metadata:
`/tmp/oracle-nbf01-rework5-gate/luna_launch.meta.json` SHA-256
`8629358179637315abc4a40cd2baa37b5dca658108e7d67b43e7b6b24cdf8cfe`. File
records `status=completed`, `exit_code=0`, `elapsed_seconds=1353.018`.

Every bound identity listed in the gate brief was independently rehashed and
matched, including historical attempt-4 artifacts labeled historical. Owned
tracked-production diff independently reproduces
`7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`.
`tests/arnold_pipelines/megaplan/test_incident_ledger.py` is unchanged versus
`origin/main` (blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`). Scope
remains the five modified production files, new `incident/disposition.py`, and
the eight named new test modules. RW-CUSTODY remains MET.

Oracle independently reran focused `123 passed in 85.67s` (stdout SHA-256
`5830451a261fd1c7f05b0cfd9641e4536d99619bac53f2ee1af5e72a6d82c71e`) and legacy
`78 passed in 2.90s` (stdout SHA-256
`589e6060d4b690e3d1635d2bd289e1848d3e76dd708f9ece3e5554b764b25353`). Luna
independently reran focused `123 passed in 52.35s` (stdout SHA-256
`e47d84bb8367f5a4c5b1c2abc109385c159c72563398ce3c661ef4ebdb08dba7`) and legacy
`78 passed in 4.67s` (stdout SHA-256
`2ec1056eb93e9ec3ef87de80f5228ddbdaad56d5c652c84f93c05025fbf6b94b`). Counts
remain observations, not targets. `py_compile` and `git diff --check` exit 0
with empty-stream SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Historical evidence remains historical and was not rewritten: start-gate 52→61,
unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`,
failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`,
attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`,
attempt-2 production digest `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`,
attempt-3 production digest `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`,
attempt-4 production digest `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`.
Current candidate digest `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`
is not an attempt-4 target.

Luna recommended `RECOMMEND_ACCEPTED_ISSUES`. Oracle independently re-read the
cited producer/append/reserve/matrix symbols and reproduced the attempt-4
coherent-forgery attack plus the named RW5-02 public-terminal loop. The RW5-01
blocker is closed at `_append_nbf` / `validate_nbf_event` / `reserve()`. The
RW5-02 named-proof hole remains.

## Hard gates

| Gate | Status |
| --- | --- |
| One fresh immutable attempt-5 Luna execution receipt/finding | **MET** |
| Exactly one fresh independent Luna full review at required paths | **MET** |
| Candidate/diff and independent test-transcript digests recorded | **MET** via Luna review plus Oracle rehash/rerun |
| North Star disposition, KISS/YAGNI stated by Luna and Grok | **MET** as statements |
| All frozen NBF-01 must criteria met with behavioral evidence | **NOT_MET** |
| 52-vs-61 and `4aee815d…` treated as historical, not rewritten | **MET** |
| RW-CUSTODY unchanged | **MET** |

`PASS_BATCH_1` is unavailable because C02/C13 remain incomplete as the frozen
named four-door proof, even though source validators reject illegal pairings.

## Criterion dispositions

Statuses: `MET` | `NOT_MET` | `UNEVIDENCED`. Oracle confirmation is against the
post-attempt-5 candidate, Luna's isolated `/tmp/oracle-nbf01-rework5-luna-review/`
transcripts, and Oracle's independent `/tmp/oracle-nbf01-rework5-grok/` probes.

### NBF-01 acceptance criteria (tasklist)

| ID | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| C01 | Strict round-trip of scheduling / six outcome kinds | **UNEVIDENCED** | Attempt 5 correctly did not reopen C01-as-`PhaseResult.from_dict` overweight. |
| C02 | Invalid kind/state/payload combinations reject | **NOT_MET** | Source constructors, `from_dict`, `validate_nbf_event`, and public `append_terminal_outcome` reject illegal pairings when given correctly shaped `DispatchOutcome` records. Named `test_dispatch_outcome_incompatible_payload_matrix` still only extends decode/validation/`_append_nbf` for the worker-success pairing. Named `test_incompatible_matrix_rejects_at_public_terminal_append` feeds incomplete dicts; Oracle reproduction rejects with missing `DispatchOutcome` fields, not the intended payload-family error. |
| C03 | `no_launch` cannot serialize with `launch_state=accepted` | **MET** | Constructor plus focused transcript. |
| C04 | `worker_disposition` required context | **MET** | Constructor plus named context tests. |
| C05 | Worker disposition cannot carry provider-exhaustion or no-launch state | **MET** | Constructor and `validate_nbf_event`. |
| C06 | Maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)` | **MET** | Classify/append mapping tests. |
| C07 | Mapping validates exactly one already-committed matching disposition | **MET** as sequential CAS | Locked identical-replay. Concurrent distinct-ID proof is C09. |
| C08 | Never coerced into ordinary failure | **MET** | Named coercion test. |
| C09 | Duplicate linkage idempotent; conflicting linkage/kinds reject | **MET** | Distinct-ID two-process terminal linkage retained. |
| C10 | Persisted accepted launch required | **MET** | Marker-bound terminal writer retained. |
| C11 | Disposition breaks consecutiveness without degradation | **MET** as named proof | Keyed reducer plus non-latest named tests. |
| C12 | `no_launch` produces no worker terminal/fingerprint/provider/streak | **MET** | Terminal writer rejects `no_launch` / `unresolved_launch`. |
| C13 | Worker / observed-death / non-worker reject incomplete or fabricated identities | **NOT_MET** as named proof | `_typed_worker_identity` and independent probe reject missing/bare/incomplete identities. Named identity test still omits direct invalid construction and public `append_terminal_outcome`; observed/non-worker named coverage remains selected omissions. |
| C14 | OOM requires positive cgroup evidence; unknown death remains unknown | **MET** | Legal positive OOM and unknown-death append paths retained; Oracle probe accepted both. |
| C15 | TERM and KILL ladder IDs are distinct | **MET** | Named test remains. |
| C16 | Semantic fingerprint excludes volatile liveness and logical/family IDs | **MET** | Named provider/fingerprint test. |
| C17 | Route-liveness digest absent from fingerprint and provider-failure key | **MET** | Same named test. |
| C18 | Same projection key + fingerprint contend for one reservation | **MET** | Real two-OS-process `fcntl.flock` race. |
| C19 | Only allowlisted reason-specific producers may mint changes | **MET** | `from_dict` raises. `validate_nbf_event` and `_append_nbf` reject unbound wire. Public producer still requires typed handles. Independent Oracle probe: forged `validate_nbf_event` rejected; `_append_nbf` rejected; `_append_nbf_locked` rejected; public append rejected; `reserve()` of unpersisted forged id rejected. |
| C20 | Producer, evidence, subject, version, before/after, provider-key binding validated | **MET** | `_validate_producer_binding` plus `_append_nbf(..., _changed_precondition=obj)` byte-compare. Mismatched handle+payload rejected `changed precondition is not producer-derived`. setattr-forged object rejected `snapshots are not producer-derived`. |
| C21 | Forged unequal content IDs or provider-failure-key transitions reject | **MET** | Original attempt-4/5 coherent recomputation of after snapshot, after key, content IDs, evidence digest, and event ID is rejected at every caller-visible NBF door and does not project via `_append_nbf`. |
| C22 | Valid changed-precondition consumed at most once | **MET** | Valid reader appends, projects unconsumed, consumes once; second consume rejected. |
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
| C39 | Durable two-scan state survives restart; TTL, scan separation, identity equality | **MET** | Named test now mutates/omits `second_evidence` and `second_evidence_digest`. Independent Oracle probe: wrong evidence rejected; omitted helper evidence `TypeError`; omitted ledger digest rejected; matching consume accepted; second consume rejected. Restart/replacement/expiry/one-consumer tests remain. |
| C40 | Ledger lock, append, schema, projection-version, and cache failures fail closed | **UNEVIDENCED** | Attempt 5 correctly did not expand cache-mismatch. |
| C41 | Disposition CLI schema validation, acknowledgements, and exit codes match §4.21 | **MET** | Independent Oracle subprocesses: 0 (`409aac1d…`), 2 malformed (`45c31321…`), 2 schema (`2525d332bcb419a8…`), 3, 4 (`d66b73aa…`), 5 missing (`ba1b0851…`), 5 expired (`4a94dd27…`), 5 consumed replay (`7fe9e01d…`). Status 0 is one JSON ack and does not signal. |

### Batch 1 checkpoint

| ID | Checkpoint | Status |
| --- | --- | --- |
| CP01 | Every NBF-01 focused test passes | **MET** as pytest gate only (Oracle: `123 passed in 85.67s`; Luna: `123 passed in 52.35s`). Does not cure named-proof incompleteness. |
| CP02 | Schema fields and legal transitions match owned §§4.4–4.13, §4.16, §§4.19–4.21 | **NOT_MET** — C02 named matrix and C13 completeness. |
| CP03 | `DispatchOutcome.kind=worker_disposition` is lossless and maps exactly once | **MET** |
| CP04 | One incident-ledger authority | **MET** for journal count / lock door. `_append_nbf` no longer mints unbound changed-precondition authority. |
| CP05 | Accepted exhausted worker outcomes are the only increment inputs | **MET** |
| CP06 | `provider_recovery_verified` remains single-use retry authorization | **MET** |
| CP07 | Success resets; different-key rekeys at one; ordinary/disposition break consecutiveness | **MET** as named keyed proof. |
| CP08 | Composite transition and child reservation remain one append with post-commit receipt | **MET** |
| CP09 | No-launch, unresolved, ordinary failure, provider exhaustion, and worker disposition are mechanically distinct | **MET** for type/state; illegal payload named matrix remains (C02). |
| CP10 | No second journal, store, prepare/commit, scheduler, rotator, or policy owner | **MET** |
| CP11 | Crash, contention, replay, torn-write, linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass | **NOT_MET** | Real races/crashes/TTL exist; named C02/C13 four-door proof remains incomplete. |

### Rework tasks

| ID | Status | Evidence |
| --- | --- | --- |
| RW5-01 | **MET** | Public producer, `validate_nbf_event`, `_append_nbf`, `_append_nbf_locked`, projection, and `reserve()` reject the prior coherent forgery. Valid reader still appends and consumes once. |
| RW5-02 | **NOT_MET** | Independent production behavior rejects all six kinds at the four doors. Named tests still do not feed correctly shaped `DispatchOutcome` records through public `append_terminal_outcome` for every kind, and identity coverage is still selected. |
| RW5-03 | **MET** | Wrong and omitted `second_evidence`/`second_evidence_digest` reject; matching consume-once remains. |
| RW4-01 | **MET** after RW5-01 | Historical attempt-4 hole closed at the canonical NBF append door. |
| RW4-02 | **NOT_MET** | Same named four-door incompleteness as RW5-02. |
| RW4-03 | **MET** | Required non-latest / recovery / lease names remain green. |
| RW4-04 | **MET** | Distinct-ID terminal race and post-append composite crash/reopen proofs remain. |
| RW4-05 | **MET** after RW5-03 | CLI 0/2/3/4/5 independently proved. Confirmation evidence-digest mismatch/omission now named. |
| RW4-06 | **MET** | Attempt-5 finding/receipt bind HEAD, source, production diff, per-file inventory, dedicated gate-command transcripts, and verbatim broad sweep. |
| RW5-GATE | **NOT_MET** | This Oracle gate returns `ACCEPTED_ISSUES`. |
| RW-CUSTODY | **MET** | Custody SHA `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` unchanged. |

### A3 dispositions

| A3 item | Status | Hole closed? |
| --- | --- | --- |
| A3-01 | **MET** | Fully populated terminal without persisted accepted marker rejects. |
| A3-02 | **NOT_MET** | Named matrix is still not a complete four-door six-kind proof. |
| A3-03 | **MET** | Coherent recomputed forgery rejected at `validate_nbf_event` and `_append_nbf`; not projected via those doors; `reserve()` of the unpersisted id rejected. |
| A3-04 | **MET** | Required non-latest named tests are present. |
| A3-05 | **MET** | Canonical probe binding and negative matrix are present. |
| A3-06 | **MET** | Distinct terminal race and post-append crash are present. |
| A3-07 | **MET** | CLI complete; confirmation evidence-digest named matrix now present. |
| A3-08 | **MET** | Attempt-5 executor inventory/stream completeness is present. |
| A3-09 | **MET** | Unofficial `reserve_provider_route_child_with_receipt` remains absent. |

## Independent probe results

### RW5-01 authority closure

Oracle rebuilt a valid `produce_source_revision_changed` event, mutated
before/after snapshots and both provider keys, recomputed `before_content_id`,
`after_content_id`, `evidence_digest`, and `event_id`, then probed every
required door. Transcripts:
`/tmp/oracle-nbf01-rework5-grok/rw5_01_authority.json`
(`342887435a397f9a0132405fcee60fad5c63fbf24ddfa03005dd0a8fa2774b3c`),
`rw5_01_bypass.json`
(`12c13eb5111a089da200966f4ce770c2e1e633d4a908123f284a52872ab5b2e0`),
`rw5_01_original_attack.json`
(`cb4d6e564f92723df08eeab331805755508e83bbd7a7a7297e9842bbadb3200e`).

| Door | Result |
| --- | --- |
| `ChangedPrecondition.from_dict(forged)` | rejected `missing fields: ['_source_handles']` |
| `validate_nbf_event(forged)` | rejected `requires a typed authoritative source handle` |
| `IncidentLedger._append_nbf(forged)` | rejected same handle error |
| `_append_nbf_locked(forged)` | rejected same handle error |
| public `append_changed_precondition(forged)` | rejected missing-handle error |
| `reserve(..., changed_precondition_event_id=forged["event_id"])` before persist | rejected `missing or already consumed` |
| `_append_nbf(forged, _changed_precondition=valid_obj)` | rejected `not producer-derived` |
| setattr-forged object public append | rejected `snapshots are not producer-derived` |
| valid reader append / consume once / second consume | accepted / accepted / rejected |

`validate_nbf_event(..., _allow_persisted_changed_precondition=True)` still
accepts a self-consistent wire snapshot. That flag is used only by
`read_nbf_events` / `_project_records` replay of already-committed NBF rows.
It is not a caller minting door.

Direct `_IncidentEventJournal._emit_locked` of a forged payload, invoked as an
internal journal primitive rather than `_append_nbf`, does persist and can
later authorize `reserve()`. That is not the RW5-01 attack surface named by
the packet (`from_dict`, `validate_nbf_event`, `_append_nbf`/`_append_nbf_locked`,
projection via those doors, `reserve()`). It is residual journal-primitive
exposure, not a fourth implementation issue and not a reason to reopen RW5-01.
No second journal, signing service, or generic producer bypass was added.

### RW5-02 complete matrix

Independent production-behavior probe
`/tmp/oracle-nbf01-rework5-grok/rw5_02_matrix.json`
(`7e315953d7a2f81c8145645b8e5599d0875411a803006a3fd590e50504ad57b1`)
rejects all six incompatible kinds at construction, `from_dict` of complete
records, `validate_nbf_event`, public `append_disposition`, and public
`append_terminal_outcome`. Missing/bare/incomplete worker identities reject.
Legal OOM and unknown-death appends succeed.

Oracle then reproduced the *named* public-terminal loop exactly as written in
`test_incompatible_matrix_rejects_at_public_terminal_append`. All six cases
reject with `missing DispatchOutcome fields: [...]`, not the payload-family
errors. `append_terminal_outcome` converts dicts via `DispatchOutcome.from_dict`
first (`ledger.py:684-687`). Incomplete named dicts never reach the intended
semantic door. That is the remaining RW5-02 hole: named proof, not source
acceptance of illegal payloads.

### RW5-03 confirmation evidence equality

Independent probe
`/tmp/oracle-nbf01-rework5-grok/rw5_03_confirmation.json`
(`c3869a5a17bf52f724382d6da21042c827fa9f34e4621083fa83c3e5d44f887b`):

- wrong PID/start/progress/incarnation/cause reject
- wrong `second_evidence={"alive": False}` rejects `confirmation evidence identity mismatch`
- omitted helper `second_evidence` raises `TypeError`
- omitted ledger `second_evidence_digest=None` rejects
- matching evidence consumes once; second consume rejects

## Broad-suite relevance classification

Luna independently reran `pytest -q tests/arnold_pipelines/megaplan` (exit 2;
stdout SHA-256
`d7a182fedf68bad45198222f2141b63a0d957b31dac30479c089a08db81f2cb6`).
Executor broad stdout SHA-256
`5a967bd2465a63ea0e7dcd6498840ae24cbcb8a2e524e64c7d4426111e1f09bc`.
Both collection failures remain:

1. `test_cli_check_validator.py` → `arnold.workflow.validator` → `arnold.agent.costing.model_resource_capabilities`.
2. `test_key_pool_codex.py` → `arnold.agent.run_agent` → `arnold.agent.tools.terminal_tool` → `tools.environments.singularity`.

Both modules are absent on the candidate and absent at `origin/main`. No owned
attempt-5 file introduced, removed, or newly reached either import.
Classification for both: **PRE_EXISTING_OUT_OF_SCOPE_BLOCKER**. This reduces
broad-suite coverage and does not waive any NBF criterion.

## Preserved prior-MET result

Independently confirmed intact: one `_IncidentEventJournal` + sequence-sidecar
flock; NBF writes still enter `_locked` / `_append_nbf_locked` for the public
producer path; C03–C12, C14–C18, C22–C38, C41; CP04 journal count, CP05
increment rule, CP06–CP08, CP10; real two-process reservation contention; owned
source scope; RW-CUSTODY; historical-evidence integrity; CLI 0/2/3/4/5.
Attempt 5 additionally closed RW5-01/RW5-03/A3-03/A3-07 without opening a
second journal or later-batch door. Preservation is not Batch 1 acceptance.

## North Star

1. **One door per invariant — MET for the changed-precondition primitive;
   NOT MET for Batch 1 as a whole.** One journal and one flock remain.
   `_append_nbf` no longer mints unbound changed-precondition authority.
   Named C02/C13 proof still does not close the four-door payload invariant.
2. **Deaths speak — foundation only.** Typed worker / observed-death /
   non-worker records, positive OOM, legal unknown death, and a non-signalling
   CLI exist. Signal-site wiring is correctly deferred.
3. **Models are admitted, not assumed — correctly deferred.** No
   admission/catalog/live-provider caller changed.
4. **Fixes ship on main through the fixer contract — not evidenced.** No
   commit/push/merge, as required for this uncommitted gate.

### Anti-patterns

- **Single-scan verdicts as sustained truth — MET for owned confirmation
  identity.** Locked TTL/policy/evidence-digest compare now has named mismatch
  and omission proof.
- **Anonymous integer exit codes — MET for the owned CLI primitive.** Typed
  disposition records and CLI 0/2/3/4/5 are independently bound.
- **Judgment-based “healthy” claims — improved.** Terminal acceptance still
  requires a persisted accepted-launch marker. Changed precondition no longer
  accepts a well-formed caller snapshot at `_append_nbf`.
- **Identical-fingerprint redispatch without a changed precondition — MET at
  the canonical NBF append door.** Two-process reservation contends. The prior
  coherent forged change no longer appends via `_append_nbf` or authorizes
  `reserve()` from that path.

## KISS / YAGNI / scope creep

- **File scope:** MET. No admission caller, scheduler, T7/T8 policy, physical
  door, launch adapter, signal site, fallback policy, second journal, or
  rotator was added. Attempt-5 production edits are `schema.py` and `ledger.py`.
- **KISS:** MET at the RW5-01 door. `_validate_changed_precondition_wire`
  now refuses unbound caller wire unless an authoritative producer object or
  persisted-replay flag is supplied. `_source_handles` remain process-local;
  replay uses `allow_persisted` only after a committed NBF row exists.
- **YAGNI:** MET in batch boundary; no UnitOfWork / two-phase / extra
  projection service / signing framework.
- **Ceremonial validation:** NOT MET for RW5-02. Named six-kind public-terminal
  and identity tests remain shape-wrong or selected. Green 123/78 cannot
  substitute.
- **Later-batch behavior in the candidate:** MET (absent).

## Independent confirmation of Luna blockers

Oracle agrees with Luna on RW5-02 as the remaining issue and independently
reproduced it. Oracle additionally confirmed RW5-01 closure one step past Luna:
the original attempt-4/5 coherent-key-change forgery is rejected at
`validate_nbf_event` and `_append_nbf`, does not project through those doors,
and cannot authorize `reserve()` unless an internal `_emit_locked` write is
used. That internal primitive is not the frozen RW5-01 door.

Luna's first CLI `status-2-schema` transcript in `cli-cases.json` used a
non-directory ledger root and exited 4. Luna's later `cli-final-cases.json`
corrects it to exit 2 with stderr SHA-256
`2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee`, matching
Oracle's independent schema-invalid run. The first transcript is a review
artifact, not a moving tree.

Luna's receipt row for RW5-02 three-module stderr is transcribed with a
truncated empty digest in one table cell (`…fb934ca495991b7852b855`); the
matching check-in row and the isolated `rw5-02-modules.stderr` file are the
full empty digest. Transcription error only.

## Residual issues and smallest next action

Remaining issue: **RW5-02 / C02 / C13 / RW4-02 / A3-02 named four-door proof.**

Smallest next triage action, without widening frozen scope:

In `tests/arnold_pipelines/megaplan/test_worker_disposition.py`, rewrite
`test_incompatible_matrix_rejects_at_public_terminal_append` and complete
`test_dispatch_outcome_incompatible_payload_matrix` so every one of the six
incompatible kinds is a correctly shaped `DispatchOutcome`/`to_dict()` record
exercised at construction, `from_dict`, `validate_nbf_event`, public
`append_terminal_outcome`, and public `append_disposition`. Extend
`test_typed_identity_matrix_rejects_missing_and_fabricated_worker_at_all_doors`
and the observed/non-worker named test with the same four doors for missing and
fabricated typed identities, keeping legal OOM/unknown-death/non-worker
positives. Do not reopen C01, C19–C21, C39, C36–C38, C40, or later-batch files.

```text
ACCEPTED_ISSUES
```
