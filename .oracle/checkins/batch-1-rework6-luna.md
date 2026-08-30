RECOMMEND_PASS_BATCH_1

# Independent Batch 1 rework-6 review — NBF-01

## Candidate binding

- Reviewer: GPT-5.6 Luna, high reasoning; independent reviewer, not executor or Oracle.
- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- `origin/main`: `798c50619204010ed3f4297fbb57988fe9381924`
- Merge-base: `798c50619204010ed3f4297fbb57988fe9381924`
- Frozen plan/tasklist/North Star/custody identities matched the supplied values. The final owned-file inventory and scope transcript are under `/tmp/oracle-nbf01-rework6-luna-review/`.
- Six-file and five-file tracked-production diff both independently hash to `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`.
- Changed `arnold_pipelines/tests` scope is exactly the five tracked production files, untracked `incident/disposition.py`, and the eight named new test files. `test_incident_ledger.py` remains unchanged at SHA-256 `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`, blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`.

## RW6-01 independent proof

The final named-three suite passed `28 passed`; the focused nine-module suite passed `124 passed`. The filtered named proof passed `2 passed, 22 deselected`, and the terminal filter passed `1 passed, 1 deselected`.

The independent payload probe (`payload-matrix-00.stdout`, SHA-256 `03eb77863ca365119b2e3cf9cbcfc21ae637de279f5b7c668f74bc7bb8dcf9c6`; structured command transcript SHA-256 `95097d508be10c551faed1e95dbbde7af9e1a7acf00bc34701e61d60554b8f0e`) drove all six incompatible combinations through direct construction, complete `to_dict()`/`from_dict`, `validate_nbf_event`, public `append_terminal_outcome`, and public `append_disposition`:

- `no_launch + success_payload`
- `unresolved_launch + structured provider_evidence`
- `success + terminal_failure`
- `ordinary_terminal_failure + success_payload`
- `provider_exhausted + disposition_id`
- `worker_disposition + success_payload`

Direct/decode/public-terminal errors were payload-family errors; validation/public disposition errors were the corresponding terminal-family errors. Legal scheduling kinds still reached `scheduling outcomes have no worker terminal event` at the legal terminal door, while illegal scheduling payloads failed at decode as required. The same probe covered missing, bare-string, wrong-type, incomplete, non-positive PID, and malformed host/boot worker identities at direct/decode/validation/public terminal/public disposition doors. It accepted legal worker disposition, observed unknown death, and non-worker lifecycle records.

The named tests now use complete records and exact intended error families. Observed-death and non-worker matrices cover missing/fabricated subject, cause, killer, victim/lifecycle identity, wrong schema version, and worker-cause boundaries at all applicable doors. `ObservedProcessDeath.__post_init__` now rejects non-mapping `victim_identity_evidence` while empty mappings still reject as missing evidence. A reconstructed attempt-5 `schema.py` with only that guard removed hashes exactly to the supplied old SHA-256 `5c150cdc5a55769a209f216ea7954831f76f8aae64606bf36a14a003312a27b1`; it accepts a fabricated non-empty victim string. The old partial six-kind matrix shape independently reproduced the old `missing DispatchOutcome fields` failures. The attempt-6 production delta is exactly the two-line typed-mapping guard plus its error line (`schema-correction-00.stdout`, exit 1 as expected for `diff -u`).

## Closed obligations and regression preservation

- **RW5-01 / C19–C21:** independent coherent forgery rebuilt before/after snapshots, content IDs, evidence snapshot/digest, both provider-failure keys, and event ID. `from_dict`, `validate_nbf_event`, `_append_nbf`, `_append_nbf_locked`, public append, forged reservation authorization, and forged consume all rejected. The forged ID never projected; a legitimate reason-specific producer appended and consumed once, and the second consume rejected. Transcript `changed-precondition-00.stdout`, SHA-256 `8fb4acee6fca22a6419bab2b67df8c70afe4bb008311f297a01bff06bb233ab5`.
- **RW5-03 / C39:** wrong second evidence rejected with `confirmation evidence identity mismatch`; omitted helper evidence raised `TypeError`; omitted ledger digest rejected; matching evidence consumed once; replay rejected. Reopen preserved consumed state and original expiry. Transcript `confirmation-00.stdout`, SHA-256 `90f91376606bfa1be4336f360fc16b768be5c40007a46b2cb1cd411208e7e76a`.
- **C41:** independent real subprocess matrix returned statuses `0, 2, 2, 3, 4, 5, 5, 5` for valid, malformed, schema, append failure, invalid location, missing confirmation, expired confirmation, and consumed replay. Corrected matrix manifest SHA-256 `9804b5a2f9fae2d3b872f6870cc1fda59af551833c1c299420f1776f6cdd50b0`; command transcript SHA-256 `0511a594bd4aeb3e67779645bb57dc28aa3d78b0c00c83eea0537515194a9bce`.
- **Crash/replay/CAS/provider:** focused suite passed and preserved one journal/sequence-sidecar lock, same-fingerprint contention, composite atomicity, post-commit receipt derivation, torn-write rejection, terminal projection-before-closure, keyed provider streaks, probe lease isolation, recovery single use, and reconciliation behavior.
- `py_compile` and `git diff --check` both exited 0 with empty-stream SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## C01–C41 dispositions

| Criterion | Disposition | Evidence |
|---|---|---|
| C01 | UNEVIDENCED | Explicitly excluded overweight `PhaseResult.from_dict` expansion; not reopened. |
| C02 | MET | Complete six-kind/four-door named matrix and independent probe with intended error families. |
| C03 | MET | `DispatchOutcome` state/kind checks; focused suite. |
| C04 | MET | Accepted worker-disposition receipt/fingerprint/phase/spec/identity/timing requirements; focused suite. |
| C05 | MET | Provider/no-launch/ordinary/success payload exclusion for worker disposition. |
| C06 | MET | Lossless `worker_disposition` to canonical terminal kind. |
| C07 | MET | Existing committed disposition and matching-context linkage required. |
| C08 | MET | Coercion to ordinary failure rejected. |
| C09 | MET | Distinct terminal linkage and concurrent ledger tests. |
| C10 | MET | Persisted accepted controlled-adapter marker required. |
| C11 | MET | Keyed streak break without provider degradation. |
| C12 | MET | No-launch/unresolved have no terminal projection. |
| C13 | MET | Complete worker, observed-death, and non-worker identity matrices at applicable doors. |
| C14 | MET | Positive cgroup OOM and explicit unknown death remain legal. |
| C15 | MET | TERM/KILL deterministic IDs differ. |
| C16 | MET | Fingerprint excludes volatile and logical/family identity. |
| C17 | MET | Route-liveness digest excluded from semantic/provider keys. |
| C18 | MET | Same projection/fingerprint reservation key contends across logical IDs. |
| C19 | MET | Coherent forged changed precondition rejected at every required authority door. |
| C20 | MET | Producer/evidence/subject/version/snapshot binding enforced. |
| C21 | MET | Recomputed coherent forgery cannot persist, project, or authorize. |
| C22 | MET | Valid changed-precondition consumption is single use. |
| C23 | MET | Probe lease and recovery authorization primitives preserved. |
| C24 | MET | Key-changing producer rekeys; key-preserving producer does not. |
| C25 | MET | Two-process reservation contention has one winner. |
| C26 | MET | Composite route-child event has one record and no child receipt input. |
| C27 | MET | Fresh replay reproduces receipt byte-for-byte. |
| C28 | MET | Torn and pre/post-append crash tests pass. |
| C29 | MET | Terminal provider/fingerprint projection precedes closure. |
| C30 | MET | Matching exhausted worker outcomes increment. |
| C31 | MET | Nonmatching key starts/rekeys at one. |
| C32 | MET | Applicable success resets its keyed streak. |
| C33 | MET | Ordinary failure/disposition breaks consecutiveness without degradation. |
| C34 | MET | Probe/recovery events preserve the streak. |
| C35 | MET | Scheduling/no-launch/unresolved/time/liveness do not mutate streak. |
| C36 | MET | Positive no-launch, recovered terminal, and ambiguous reconciliation retained. |
| C37 | MET | Recovered disposition links existing evidence without duplication. |
| C38 | MET | Blind/conflicting/accepted-launch no-launch releases reject. |
| C39 | MET | Wrong/omitted digest, restart, expiry, replacement, and one-consumer proof. |
| C40 | UNEVIDENCED | Explicitly excluded cache/projection-version expansion; not reopened. |
| C41 | MET | Independent real subprocess status 0/2/3/4/5 matrix. |

## CP01–CP11 dispositions

| Checkpoint | Disposition | Evidence |
|---|---|---|
| CP01 | MET | Focused nine-module suite: 124 passed. |
| CP02 | MET | C02/C13 named matrices now complete; owned schema transitions match frozen contract. |
| CP03 | MET | Explicit lossless worker-disposition mapping and one existing disposition linkage. |
| CP04 | MET | One `_IncidentEventJournal`, one sequence-sidecar flock, one NBF append authority. |
| CP05 | MET | Only accepted provider-exhausted terminal outcomes feed the keyed observation reducer. |
| CP06 | MET | Recovery authorization remains lease/evidence-bound and single-use. |
| CP07 | MET | Success reset, different-key rekey, ordinary/disposition break tests pass. |
| CP08 | MET | Composite transition/child reservation and post-commit receipt replay pass. |
| CP09 | MET | No-launch, unresolved, ordinary, provider, and worker-disposition paths remain mechanically distinct. |
| CP10 | MET | No second journal/store/prepare-commit/scheduler/rotator/family lease. |
| CP11 | MET | Crash, contention, replay, torn-write, linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass. |

## RW status and North Star alignment

- **RW6-01:** MET. Named tests and independent four-door payload/identity probe now prove the intended contracts.
- **RW5-01:** MET and not reopened. Coherent recomputation cannot regain authority.
- **RW5-03:** MET and not reopened. Evidence equality and single consumption hold.
- **One door per invariant:** MET for this Batch-1 primitive. One journal, one lock, one terminal writer, one disposition helper, one producer boundary. Admission/dispatch/signal physical doors remain deliberately deferred to later batches, not duplicated here.
- **Deaths speak:** MET for the owned foundation. Worker, observed-death, and non-worker records are typed; OOM has positive evidence; TERM/KILL identities differ; CLI records and never signals. Real signal-site wiring remains later scope.
- **Models admitted, not assumed:** UNEVIDENCED and correctly deferred; no admission/catalog/live-membership behavior is owned here.
- **Fixes ship on main:** UNEVIDENCED for this dirty, uncommitted candidate; delivery is a later guarded checkpoint.
- **Anti-patterns:** single-scan truth is prevented by durable equality/TTL/identity confirmation; anonymous exits are not used by the owned CLI; accepted launch markers and canonical records provide positive evidence; identical-fingerprint redispatch requires a changed precondition.
- **KISS/YAGNI:** MET. The candidate uses one journal/store/projection and no second scheduler, rotator, family lease, signing framework, generic producer escape hatch, or speculative admission machinery. The only production delta in rework-6 is the necessary typed victim-evidence guard.

## Recommendation and next action

No blocking issue found. The smallest next action is the separately authorized Grok 4.6 Oracle gate. This review does not issue an Oracle token, start Batch 2, perform a second review, or modify any candidate source/test/plan/custody/history artifact.
