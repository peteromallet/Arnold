# Independent Batch 1 rework-4 review — NBF-01 (GPT-5.6 Luna)

You are the **independent Batch 1 rework-4 reviewer**, not the executor and not
the Oracle. You are GPT-5.6 Luna at high reasoning. Your job is one complete,
evidence-cited full review of the post-attempt-4 NBF-01 candidate against the
frozen contract and the supplemental attempt-4 rework packet. This is not a
smoke-test rerun and not a restatement of the executor narrative. Do not reuse
any attempt-1, attempt-2, or attempt-3 command transcript, probe, ledger root,
or conclusion as current evidence. Attempt-3 artifacts are historical context
only.

Do not implement, repair, stage, commit, push, merge, rebase, reset, clean, or
edit production, test, plan, frozen tasklist, North Star, custody, historical
Batch-1 / attempt-1 / attempt-2 / attempt-3 receipts/findings/check-ins, or any
rework packet. Do not start Batch 2. Do not fan out a second review. Do not
self-issue `PASS_BATCH_1`.

Worktree: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
Branch: `megado-nbf-guard-0826`
Python: prefer `PYENV_VERSION=3.11.11 python` or the repo venv if present.
Write pytest/CLI/probe transcripts only under `/tmp/oracle-nbf01-rework4-luna-review/`.
Temporary probes and ledgers must live under that isolated root or a fresh
temporary child path, never in the repository. Do not overwrite the executor
transcripts already at `/tmp/oracle-nbf01-rework4-luna/`.
The only worktree writes authorized are the two output files named below.

## Complete North Star (mandatory; judge alignment explicitly)

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

Advance that end state without widening `.oracle/agent_goal.md`. Critique for
elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag
overengineering, not just bugs.

## Independence and source identity

Evaluate the candidate actually on disk, not the executor narrative.

Oracle independently verified these identities immediately before this brief.
Re-verify each with `shasum -a 256` / `git rev-parse` / `git hash-object`. A
mismatch is an evidence-integrity issue, not permission to continue as if bound.

| Artifact | Expected identity |
| --- | --- |
| Repository | `/Users/peteromalley/Documents/Arnold-oracle-nbf` |
| Candidate branch | `megado-nbf-guard-0826` |
| Candidate HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Source and merge-base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` (frozen) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Model-policy receipt | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Tasklist freeze v8 receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` |
| Attempt-4 packet `.oracle/rework/batch-1-attempt-4.md` | `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534` |
| Attempt-4 triage brief | `d6c559d694c006d4fd310ae706779604ebe228f713a27a40669d6c5c1c040c0f` |
| Attempt-4 triage receipt | `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c` |
| Attempt-4 execution brief | `25b981e7e20cda6e7aff2027074631dc3b713ec11b0015df81238138e484c79d` |
| Attempt-4 executor finding | `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1` |
| Attempt-4 executor receipt | `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f` |
| Candidate production diff SHA-256 | `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41` |

Historical attempt-3 context (label historical; do not treat as current proof):

| Historical artifact | SHA-256 |
| --- | --- |
| Attempt-3 gate brief | `5b062d0ded7552ce01bb7b4a7231a349419102a219c967c9a05cfbf46f2fdc01` |
| Attempt-3 packet | `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779` |
| Attempt-3 triage receipt | `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b` |
| Attempt-3 executor finding | `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f` |
| Attempt-3 executor receipt | `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f` |
| Attempt-3 Luna review check-in | `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd` |
| Attempt-3 Luna review receipt | `ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425` |
| Attempt-3 Grok check-in | `4bd93c1d24e55c1860add92abbce5c44c979c2d0b83dd63b1ceb798db783af02` |
| Attempt-3 Grok receipt | `95ec60c0f981217500b9922ac86ffb95d6c60036d39ea32d07761731716c3a30` |
| Attempt-3 production diff | `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8` |

Executor claimed post-attempt-4 tracked production diff digest (must independently
reproduce with the exact command below):

```bash
git diff origin/main -- \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  | shasum -a 256
```

Claimed output: `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`

Oracle independently hashed every owned production/test file immediately before
this brief. If the tree you inspect differs, stop and recommend
`RECOMMEND_ACCEPTED_ISSUES` for a moving candidate; do not silently review a
different tree.

| Owned file | SHA-256 | git blob |
| --- | --- | --- |
| `incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` |
| `incident/ledger.py` | `da256e9d10763d1f5e76a13cacb95ae6d61a3ca6e95c42ae4d4f702e3c3061fe` | `dab84bf37a52396b7b6de440e44c199d5bc342e0` |
| `incident/schema.py` | `e32c111c077cced274162e51df1d3b0623b99a2933b390928f1356fe34402004` | `f85ec2172ec1e36087e2927f796d8a61e72af97a` |
| `orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `incident/disposition.py` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` | `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3` |
| `test_changed_precondition_producers.py` | `ed21611737f05d74aecaa1f41b4a8af37baf59d488c467b232d77acf992b3cea` | `11813a7d986556b203497b2bad055eaa94aba550` |
| `test_incident_ledger_transactions.py` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` | `c91963087ae35fce9f50ae322663825e4642bb59` |
| `test_provider_route_projection.py` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` | `6de73b1e16d59ade8c22c5428dfdad5b660b072c` |
| `test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `test_supervision_confirmation.py` | `73be8fb3f19e903f5b48680d200674e547aa4c4b111495e92b19ab7d1fe7a9d7` | `30d6200fe4acd01cb2fd653364b949adaaa93e0a` |
| `test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `test_worker_disposition.py` | `0f9c412cd85b217a132b0e84b4e2f944bf4ba4b947f1dbbbc785116e0a876d06` | `12e44bba5a1e9e99cb14886047eef240663244fb` |

`tests/arnold_pipelines/megaplan/test_incident_ledger.py` must remain unchanged
versus `origin/main` (blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`).

Do not rewrite historical evidence. Preserve as historical:

- Original start-gate receipt claimed focused **52** passed, later mutated on
  the same path to **61**.
- Unreproducible owned-source digest
  `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`.
- Prior independent Luna failed-handoff digest
  `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`.
- Attempt-1 observation focused **78** / legacy **78** and digest `e060f650...`.
- Attempt-2 owned tracked-production digest
  `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`.
- Attempt-3 owned tracked-production digest
  `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`.
- Current focused count is an observation, not a target.

If any frozen identity mismatches, record it as an issue.

## Required reads (complete, not summaries)

Read every file completely before judging:

1. `.oracle/northstar.md`
2. `.oracle/agent_goal.md`
3. `.oracle/custody.md`
4. `.oracle/receipts/model-policy-grok-switch.md`
5. `.oracle/plan.md` — complete settled plan v8, especially §§4.4–4.13, §4.16,
   §§4.19–4.21
6. `.oracle/tasklist.md` — complete NBF-01 section, frozen dispatch/terminal
   semantics, Batch 1 checkpoint
7. `.oracle/receipts/tasklist-freeze-v8.md`
8. `.oracle/rework/batch-1-attempt-4.md` (current packet)
9. Historical attempt-3 packet/check-in/receipt labeled historical
10. Attempt-4 executor finding and receipt bound above
11. Every owned production and test file listed below

Do not treat the executor receipt as proof. Reproduce the diff, named tests,
CLI statuses, required behavioral names, and independent probes yourself under
`/tmp/oracle-nbf01-rework4-luna-review/`.

## Owned candidate paths (NBF-01 only)

Production (may be modified vs `origin/main`):

- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- `arnold_pipelines/megaplan/incident/disposition.py` (new/untracked)
- `arnold_pipelines/megaplan/incident/__init__.py` (exports only; confirm no extra behavior)

Tests:

- `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
- `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
- `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
- `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
- `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`
- `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
- `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
- `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
- existing `tests/arnold_pipelines/megaplan/test_incident_ledger.py` (must remain unchanged)

Any change outside this set, or any later-batch behavior inside it (admission
callers, scheduling loops, T7 waits, T8 thresholds/policy, physical-door
wiring, controlled launch execution, signal-site wiring, provider fallback
decisions, second journal/store/scheduler/rotator), is out of NBF-01 scope.

RW-CUSTODY is already MET. Do not edit `.oracle/custody.md`. Keep
`f8725af516da8d4249eb0d63563c37776d80daf8` historical and
`origin/main@798c50619204010ed3f4297fbb57988fe9381924` current.

## Serial scope to validate

The attempt-4 packet's serial scope is RW4-01 → RW4-02 → RW4-03 → RW4-04 →
RW4-05 → RW4-06, followed by RW4-GATE. Validate the six accepted-issue themes:

1. C19–C21 authoritative producer and coherent-forgery resistance.
2. C02/C13/C14 strict payload and typed-identity validation.
3. C11/C32/C33/C34 keyed provider streak, recovery, and probe binding.
4. C09/C28 composite race, crash, and replay behavior.
5. C39/C41 confirmation full matrix and CLI regression behavior.
6. RW3-06/A3-08 evidence completeness.

Do not reopen C36–C38, overweight C01, expand C40, or pursue T8 policy,
environment repair, custody/history/admission/scheduler/physical-door/launch,
signal, fallback, or other excluded work.

## Capture the exact candidate

From the worktree root:

```bash
git rev-parse HEAD
git rev-parse origin/main
git merge-base HEAD origin/main
git status --porcelain=v1
git diff --name-status origin/main -- arnold_pipelines tests
git ls-files --others --exclude-standard -- arnold_pipelines tests
```

Record SHA-256 of the exact production diff command above and of each owned
untracked file. Record changed-file scope. Unrelated dirty `.oracle` planning
artifacts are not Batch 1 acceptance evidence; note them only as non-owned
noise. Do not claim a clean tree by ignoring protected artifacts.

If source or tests differ from the Oracle-bound hashes above, do not silently
review a moving tree: recommend `RECOMMEND_ACCEPTED_ISSUES` and require fresh
executor evidence for the exact tree.

## Reproduce every named command (necessary, not sufficient)

Write transcripts to `/tmp/oracle-nbf01-rework4-luna-review/` only. Record full
argv, cwd, exit status, verbatim stdout and stderr, and SHA-256 of stdout bytes
and stderr bytes for each. Do not abbreviate pytest output to a count. Empty
stdout/stderr SHA-256, when truly empty, is the full 64-hex
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Never truncate it.

Focused (frozen nine-module command):

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

Legacy:

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py
```

Packet-required subsets (reproduce independently; do not reuse executor
`.meta` files as your transcripts):

```bash
pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  -k "coherent_forged or authoritative or reader"
pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py
pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "two_process or torn or crash or contention"
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  -k "replay or receipt"
pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
```

Compile and whitespace:

```bash
python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py
git diff --check
```

Full megaplan test-directory sweep (required, with relevance protocol below):

```bash
pytest -q tests/arnold_pipelines/megaplan
```

CLI via independent subprocesses (do **not** treat pytest names as a substitute
for these transcripts). Exercise statuses 0, 2 (malformed and schema-invalid),
3 (append/lock), 4 (invalid ledger location), and 5 (missing, expired, and
distinct already-consumed replay). Record exact argv, cwd, stdin, ledger root,
verbatim stdout/stderr, exit, and both stream SHA-256 values. Status 0 must
emit one JSON acknowledgment and must not signal.

A passing test command is not sufficient if the authorization boundary,
provenance, full-field semantics, or crash/contention invariant remains
forgeable.

## Independent probe checklist (mandatory)

Independently inspect and probe, with exact paths, commands, outputs, exit
statuses, and digests:

- complete path/hash inventory and transcript/receipt integrity;
- direct and wire authorization boundaries, including authoritative producer
  provenance and protection against coherent changed-precondition forgery;
- strict payload shape and typed identity fields, including full-field
  confirmation semantics rather than partial or truthy checks;
- keyed provider streak behavior, recovery and probe binding, and cross-key
  contamination resistance;
- post-append crash durability, contention/race behavior, replay/idempotency,
  and composite failure handling;
- CLI statuses and exit codes 0/2/3/4/5, including regression coverage and
  truthful failure reporting;
- focused/adversarial and required legacy incident/phase test evidence;
- alignment with the North Star and KISS/YAGNI: one door per invariant,
  typed deaths, live admission, and no speculative or redundant machinery.

The strongest remaining historical risk is coherent changed-precondition
forgery. Independently rebuild snapshots, content IDs, evidence digest, and
event ID, then attempt decode, locked append, and locked consume. Also
exercise a valid typed authoritative-reader event that must append and
consume exactly once. Record the probe transcript under the isolated review
root.

Use current code and test behavior to distinguish a real blocker from a mere
narrative concern.

## Broad-suite missing-module relevance protocol

If `pytest -q tests/arnold_pipelines/megaplan` fails at collection because of
missing `arnold.agent.costing.model_resource_capabilities` and/or
`tools.environments.singularity`, classify each as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` only after proving:

1. the import chain is unchanged versus `origin/main`;
2. no owned attempt-4 production/test file introduced, removed, or newly
   reached either import;
3. the modules are absent on both the candidate and `origin/main`.

Record the complete sweep stdout/stderr; do not summarize. Do not repair the
environment. This reduces coverage and does not waive any NBF criterion.

## Frozen NBF-01 criteria C01–C41 and Batch 1 CP01–CP11

Classify each criterion and checkpoint `MET` | `NOT_MET` | `UNEVIDENCED` with
exact file/symbol and evidence. Do not reopen C36–C38. Do not overweight C01.
Do not expand C40. C01/C40 remaining UNEVIDENCED is context, not a new
implementation issue unless a frozen must cannot live in the eight new
modules.

Also classify RW4-01 through RW4-06, RW4-GATE, and A3-01 through A3-09.

## Binary recommendation

End with exactly one of:

```text
RECOMMEND_PASS_BATCH_1
```

or

```text
RECOMMEND_ACCEPTED_ISSUES
```

You may **not** issue `PASS_BATCH_1`. That is Grok Oracle only.

For `RECOMMEND_ACCEPTED_ISSUES`, list each issue with severity
(`blocker` | `major` | `minor`), exact file/symbol or criterion, concrete
evidence, and the smallest required correction. Do not implement corrections.
If issues remain, identify the smallest concrete attempt-5 triage action; do
not invent new scope.

A recommendation of PASS requires that every NBF-01 must criterion, every
Batch 1 checkpoint bullet, every preserved prior-MET criterion, every
RW4-01…RW4-06 acceptance criterion, A3-01..A3-09, the evidence protocol, and
preservation/scope gates are `MET` with cited behavioral evidence. Green
counts, executor claims, or an out-of-scope test-environment failure cannot
substitute for behavioral proof.

## Output files — write exactly these two

1. Full review:

```text
.oracle/checkins/batch-1-rework4-luna.md
```

Structure:

```markdown
# Luna independent review — NBF-01 / Batch 1 rework 4

- Model: GPT-5.6 Luna
- Date: 2026-08-30
- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Branch: megado-nbf-guard-0826
- HEAD: <rev-parse>
- Tasklist SHA-256: ...
- Plan v8 SHA-256: ...
- North Star SHA-256: ...
- Attempt-4 packet SHA-256: ...
- Executor finding: .oracle/findings/execution-nbf01-rework4-luna.md
- Executor finding SHA-256: ...
- Executor receipt: .oracle/receipts/execution-nbf01-rework4-luna.md
- Executor receipt SHA-256: ...
- Owned production diff SHA-256: ...
- Isolated transcript root: /tmp/oracle-nbf01-rework4-luna-review/

## Scope and diff
## Validation evidence
## Criterion dispositions (C01–C41, CP01–CP11)
## Rework task dispositions (RW4-01…RW4-06, RW4-GATE, A3-01…A3-09)
## Independent probes
## Broad-suite relevance classification
## Preserved prior-MET result
## North Star
## KISS / YAGNI / scope
## Evidence integrity
## Issues
## Recommendation
RECOMMEND_...
```

2. Immutable review receipt:

```text
.oracle/receipts/oracle-nbf01-rework4-luna.md
```

The receipt must bind: reviewed candidate HEAD, owned production diff digest,
every test-transcript digest, every probe transcript digest, execution receipt
digest, North Star / plan v8 / frozen tasklist / attempt-4 packet digests,
check-in path and its SHA-256 after write, isolated transcript root, reviewer
count exactly one, actual commands with timestamps and exit statuses, separate
stdout/stderr/transcript digests, and a statement that you did not mutate the
candidate after those digests.

Also print the recommendation line on stdout as the last line.

Do not write `.oracle/checkins/batch-1-rework4-grok.md` or the Grok Oracle
receipt. Do not commit. Do not start Batch 2.
