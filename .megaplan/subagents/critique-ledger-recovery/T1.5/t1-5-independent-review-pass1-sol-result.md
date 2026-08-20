# HARD FAIL — T1.5 canonical `simple_fixer` independent review, pass 1

**Verdict: HARD FAIL.**

This is a local review verdict for the frozen candidate only. It is not a formal
T1.5 completion claim, owner acceptance, deployed-runtime acceptance, or evidence
that the incident/epic advanced. The candidate is not eligible for clean-lineage
integration in its reviewed form.

## Frozen candidate identity re-verification

- Read-only review worktree:
  `/private/tmp/arnold-critique-recovery-simple-fixer-20260802`
- Exact ancestor before implementation:
  `6787d6363e8fc0603092913ae877db14f3b9fff8`
- Implementation commit:
  `bf6af7db8285e56379ed12ae94af5cdb14f4c1cd`
- Implementation tree:
  `ae43595f3c6ec8ea7c48ab8ad95b802f2ddeec98`
- Evidence-only head:
  `4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a`
- Evidence-head tree:
  `066c22a540ff9983380760088e2daa9113cbb539`

Identity commands and results:

```text
git status --porcelain=v2 --branch --untracked-files=all
# branch.oid 4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a
# branch.head critique-recovery-t1-5-simple-fixer-20260802
# no tracked, staged, or untracked status entries

git rev-parse HEAD HEAD^{tree}
4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a
066c22a540ff9983380760088e2daa9113cbb539

git show -s --format='%H %T %P' bf6af7db8285e56379ed12ae94af5cdb14f4c1cd
bf6af7db8285e56379ed12ae94af5cdb14f4c1cd ae43595f3c6ec8ea7c48ab8ad95b802f2ddeec98 6787d6363e8fc0603092913ae877db14f3b9fff8

git show -s --format='%H %T %P' 4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a
4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a 066c22a540ff9983380760088e2daa9113cbb539 bf6af7db8285e56379ed12ae94af5cdb14f4c1cd

git merge-base --is-ancestor 6787d6363e8fc0603092913ae877db14f3b9fff8 bf6af7db8285e56379ed12ae94af5cdb14f4c1cd
exit 0

git merge-base --is-ancestor bf6af7db8285e56379ed12ae94af5cdb14f4c1cd 4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a
exit 0
```

The worktree was clean when admitted. Review probes used disposable scratch and
did not alter the candidate, refs, cloud/provider state, production owner state,
or checklist. A retirement subreview rechecked the same clean HEAD/tree after its
probes.

## Independently reproduced suites

Green suites were treated as observations, not as proof of the finite contract.

### Focused, concurrency, and crash suite

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider \
  tests/cloud/test_simple_fixer.py -q
......................                                                   [100%]
22 passed in 1.09s
```

### Retirement/dependency/bypass suite

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/cloud/test_simple_fixer_retirement.py \
  tests/cloud/test_progress_auditor.py \
  tests/cloud/test_repair_delegation.py \
  tests/cloud/test_wrapper_authority_bypass_gating.py \
  tests/m9/test_bypass_gating.py \
  tests/resident/test_fix_the_fixer_command.py \
  tests/test_managed_agent.py \
  tests/arnold_pipelines/megaplan/watchdog/test_repair_runner.py
75 passed in 2.13s
```

### Installed-wheel suite

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/installed_wheel \
  tests/arnold_pipelines/megaplan/test_wheel_smoke.py
7 passed in 98.51s (0:01:38)
```

### Full cloud suite, run single-flight

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/cloud -q
1395 passed, 741 skipped in 35.08s
```

The 741 skips are exactly 741 cases in 28 newly module-skipped files; they are
not incidental platform skips:

| Skipped cases | Module |
|---:|---|
| 3 | `tests/cloud/test_chain_health_terminal_shortcuts.py` |
| 11 | `tests/cloud/test_cloud_status_custody.py` |
| 2 | `tests/cloud/test_meta_repair_pause_dispatch.py` |
| 2 | `tests/cloud/test_meta_repair_trigger_custody.py` |
| 13 | `tests/cloud/test_meta_repair_wrapper_retrigger.py` |
| 7 | `tests/cloud/test_post_fixer_recovery_gate.py` |
| 6 | `tests/cloud/test_recovery_decision_systemic.py` |
| 1 | `tests/cloud/test_repair_claim_cleanup.py` |
| 35 | `tests/cloud/test_repair_custody.py` |
| 16 | `tests/cloud/test_repair_dispatch_classifier.py` |
| 24 | `tests/cloud/test_repair_goal.py` |
| 43 | `tests/cloud/test_repair_investigation.py` |
| 1 | `tests/cloud/test_repair_loop_advancement_policy.py` |
| 1 | `tests/cloud/test_repair_loop_done_chain_stale_completion.py` |
| 18 | `tests/cloud/test_repair_loop_summary.py` |
| 3 | `tests/cloud/test_repair_loop_terminal_stale_chain.py` |
| 18 | `tests/cloud/test_repair_request_hooks.py` |
| 62 | `tests/cloud/test_repair_requests.py` |
| 30 | `tests/cloud/test_repair_trigger_wrapper.py` |
| 16 | `tests/cloud/test_runtime_attestation.py` |
| 3 | `tests/cloud/test_source_initiative_repair.py` |
| 6 | `tests/cloud/test_superfixer_custody_systemic.py` |
| 18 | `tests/cloud/test_supervisor_runtime_isolation.py` |
| 1 | `tests/cloud/test_watchdog_chain_stuck_projection.py` |
| 3 | `tests/cloud/test_watchdog_finalized_wait_state.py` |
| 3 | `tests/cloud/test_watchdog_missing_spec_completion.py` |
| 7 | `tests/cloud/test_watchdog_pr_reconciliation.py` |
| 388 | `tests/cloud/test_watchdog_wrappers.py` |

## Concrete blockers

### B1 — caller assertions mint ordinary authority and execute a local effect

`AuthorityEnvelope.from_mapping()` checks only exact field names, non-empty
strings, a positive integer epoch, and equality of the caller-asserted RA and
Custody fence strings to the caller-asserted F01 fence. It never consults a
current authoritative Run Authority source, Custody lease/epoch owner, or WBC
reservation/GLEK source (`arnold/recovery/simple_fixer.py:182-220`).
`HermeticRecoveryOwner.intake()` then persists those assertions as `ELIGIBLE`
(`arnold/recovery/simple_fixer.py:537-606`). The Megaplan adapter accepts a
publicly constructible `AuthorityEnvelope` and forwards the mapping
(`arnold_pipelines/megaplan/cloud/simple_fixer.py:113-125`).

The local owner/effect path is a normal shipped import, exported by
`arnold/recovery/__init__.py:17,32` and `arnold/recovery/simple_fixer.py:1138-1143`.
Its effect gate is only a caller-forgeable boolean attribute
`__test_only_recovery_effect__` (`arnold/recovery/simple_fixer.py:306-311,410-427`).

A disposable probe normally imported the public owner, supplied a custom effect
object with that boolean, forged all F01 and RA/Custody/WBC strings, and ran the
occurrence. Result:

```json
{"counts":{"attempts":1,"claims":1,"occurrences":1},"effect_file":"MUTATED","intake_status":"ELIGIBLE","result_status":"SUCCEEDED"}
```

This is current executable behavior, not unreachable historical text.

The fixed production socket client also authenticates a responder only by the
public schema digest and does not bind peer identity, response operation, exact
occurrence, or response shape (`arnold/recovery/simple_fixer.py:314-391`).

### B2 — targeted stored-result corruption is replayed without receipt validation

`_stored_result()` accepts any non-null `result_bytes`
(`arnold/recovery/simple_fixer.py:618-627`), and `run()` returns it before claim,
authority, intent, or receipt validation (`arnold/recovery/simple_fixer.py:715-718`).
Although receipts are generated at `arnold/recovery/simple_fixer.py:667-689`, the
receipt is not verified on replay.

Reproduction: run one valid fixture occurrence, directly corrupt only the durable
attempt result with `UPDATE attempts SET result_bytes=x'...'`, then rerun the same
occurrence. Exact replay output:

```text
FORGED-RESULT
```

The checked-in corruption test replaces the whole database and expects SQLite to
error (`tests/cloud/test_simple_fixer.py:451-465`); it does not exercise forged
result/receipt replay.

### B3 — normal imported legacy internals still launch a retired repair child

`AUTOMATIC_RUN_KINDS` still includes the eight recovery kinds at
`arnold_pipelines/megaplan/managed_agent.py:44-55`, alongside the newly declared
retired set at `:57-67`. `reserve_managed_command()` accepts membership in the
former and has no retirement rejection (`:541-583`). The public
`run_managed_command()` guard exists only at `:762-769`; the importable
`_run_managed_command_locked()` has no equivalent guard (`:787-1021`) and invokes
`subprocess.Popen` at `:896-903`.

A disposable `automatic_repair` probe showed:

```text
public_guard=RuntimeError: RETIRED_RECOVERY_AUTHORITY ...
after_public_sentinel=False run_root_exists=False
internal_rc=0
sentinel=True executed
manifest_run_kind=automatic_repair manifest_status=completed
```

The replacement retirement test covers only the guarded public function
(`tests/cloud/test_simple_fixer_retirement.py:59-69`). The reservation function
and internal executor were byte-identical to the exact ancestor. This probe used
normal imports and a normal callable internal seam; it did not require interpreter
takeover.

### B4 — public `repair_source_initiative()` still mutates without the owner contract

The production function at
`arnold_pipelines/megaplan/cloud/source_initiative_repair.py:107-149` is unchanged
from the exact ancestor. It copies a source initiative tree into a caller-selected
workspace without owner service, exact owner-accepted F01 occurrence, RA grant,
Custody lease/epoch/fence, WBC GLEK, canonical claim, or effect receipt.

The implementation did not retire or tombstone the production subject. Its only
change to `tests/cloud/test_source_initiative_repair.py` was to add:

```python
pytestmark = pytest.mark.skip(
    reason="historical repair-loop source mutation route retired by M11 T1.5"
)
```

at line 5, disabling all three tests.

Disposable normal-import reproduction:

```python
import tempfile
from pathlib import Path
from arnold_pipelines.megaplan.cloud.source_initiative_repair import repair_source_initiative

repo = Path('/private/tmp/arnold-critique-recovery-simple-fixer-20260802')
relative = Path('.megaplan/initiatives/native-composition-followup.chain/chain.yaml')
with tempfile.TemporaryDirectory(prefix='t15-hostile-source-repair-') as raw:
    workspace = Path(raw)
    remote = workspace / relative
    before = remote.exists()
    result = repair_source_initiative(
        workspace=workspace, remote_spec=remote, arnold_src=repo
    )
    print(before, remote.exists(), result.repaired, result.reason)
```

Observed result:

```json
{"after":true,"before":false,"reason":"source_initiative_restored","repaired":true}
```

This live route alone disproves clauses 2, 5, 9, and 10.

### B5 — direct-module `repair_goal ensure` still mints local recovery state

`arnold_pipelines/megaplan/cloud/repair_goal.py` is byte-for-byte identical to the
exact ancestor. `ensure_repair_goal()` builds and persists an active filesystem
repair goal from caller labels at `:1008-1090`; its parser/main exposes that path
through direct module execution at `:1771-1856`. All 24 subject tests were disabled
by the new module skip at `tests/cloud/test_repair_goal.py:5`.

Disposable reproduction:

```text
PYTHONPATH=. python -m arnold_pipelines.megaplan.cloud.repair_goal ensure \
  --marker-dir <scratch>/markers \
  --session forged-session \
  --workspace <scratch>/workspace \
  --remote-spec forged:/workspace \
  --plan-name forged-plan \
  --blocker-id forged-blocker \
  --request-id forged-request
```

It exited 0 and created
`markers/repair-goals/forged-session/goal-*.json` with status `active`, the forged
labels, and a local lock. This is executable direct-module behavior, not an
unreachable body.

### B6 — fix-the-fixer authorization and v2 provenance dedupe are caller-mintable

`FixTheFixerEnvelope` treats all coordinates, implementation/backstop digests,
and verifier identity as arbitrary non-empty strings, rejecting only a verifier
label equal to the grant label (`arnold/recovery/simple_fixer.py:224-248`). The
transaction table stores only envelope/status/time (`:518-525`).
`fix_the_fixer()` records `AUTHORIZED_PENDING_INDEPENDENT_VERIFICATION` without
an independently established authority decision, verified digest form, attempt
intent, effect/result/receipt, or verifier receipt (`:1052-1114`).

A probe supplied `implementation_digest='not-a-digest'`,
`backstop_digest='also-not-a-digest'`, caller-declared authority, and three fresh
caller transaction IDs. All three became
`AUTHORIZED_PENDING_INDEPENDENT_VERIFICATION`; transaction count was 3.

Separately, `record_delegation_provenance_error()` includes free-form `detail` in
its dedupe key (`arnold/recovery/simple_fixer.py:1008-1038`). Two descriptions of
the same provenance failure and occurrence produced:

```text
obligations=2
quiet_transitions=2
```

Thus one v2 provenance failure can amplify obligations/transitions merely by
changing its wording.

### B7 — the 741 skips manufactured green coverage while live subjects remain

All 741 skips are module-wide skips introduced across the 28 files tabulated
above. At least the following production subjects remain executable and unchanged
from the ancestor while their tests are entirely skipped:

- `source_initiative_repair.py` — public workspace mutation, demonstrated above;
- `repair_goal.py` — direct-module filesystem recovery goal creation,
  demonstrated above;
- `repair_investigation.py` — ancestor-identical while all 43 subject tests are
  skipped.

Focused replacement tests coexist with these bypasses. For example:

```text
python -m pytest -q \
  tests/cloud/test_simple_fixer_retirement.py \
  tests/cloud/test_repair_goal.py \
  tests/cloud/test_repair_investigation.py
16 passed, 67 skipped
```

The candidate report's statement that historical bodies are acceptable because
an early public return makes them unreachable is also below the frozen contract.
Historical code after unconditional returns is distinguished here from the
demonstrated current behavior: no verdict relies merely on unreachable text.
The blockers above execute through public imports, direct module execution, or a
normal imported internal alias.

## Finite acceptance matrix

| # | Verdict | Basis |
|---:|:---:|---|
| 1 | **HARD FAIL** | F01 field shape is exact, but RA/Custody/WBC are accepted as caller assertions; no authoritative source validates grant revision/fence, lease/epoch/fence, or GLEK. B1. |
| 2 | **HARD FAIL** | The fixed production client has no documented fallback, but shipped importable local effect routes execute without it: the public SQLite/effect owner, `repair_source_initiative()`, and direct-module `repair_goal ensure`. B1, B4, B5. |
| 3 | **HARD FAIL** | Race/crash/budget behavior passes the focused suite, but stored result bytes are replayed without receipt validation and targeted corruption returns `FORGED-RESULT`. B2. |
| 4 | **HARD FAIL** | The canonical leaf schema rejects child/command fields, but the retired `automatic_repair` kind still launches through exported reservation plus importable internal executor. B3. |
| 5 | **HARD FAIL** | Several wrappers are real tombstones/delegates, but normal import/direct-module/internal routes remain active. Flags are not needed to reactivate them. B3-B5. |
| 6 | **HARD FAIL** | Separate transaction shape exists, but authorization, digests, and verifier are caller-mintable; transactions lack independent verifier receipts; provenance wording multiplies obligations. B6. |
| 7 | **PASS (local)** | The independently reproduced focused suite covered the immediate/reconciler race, five crash boundaries, response loss, 200 observers, stale leases, fence change, corruption/ENOSPC, and identical provenance dedupe. A separate hostile concurrency probe produced one result, one effect, and one attempt across 200 alternating trigger calls. This local pass does not cure clauses 1-6 or prove deployment. |
| 8 | **PASS (independent artifact probe), evidence gap** | Source/wheel/installed recovery files, wrappers, systemd, and container templates were byte-equivalent in disposable inspection; installed and materialized CLIs emitted identical help and exited 69 when the fixed socket was absent. However, the seven committed wheel tests are generic and contain no recovery-owner assertion; checked-in owner-absence tests use source imports or source-forced `PYTHONPATH`. |
| 9 | **HARD FAIL** | Public local effect routes remain shipped. The alleged dynamic inventory is a static JSON limited to immediate non-Megaplan children (`arnold/recovery/non_megaplan_bypass_inventory.json:1-14`) and a narrow lexical test (`tests/cloud/test_simple_fixer_retirement.py:72-89`); it misses the shipped neutral local effect API and the demonstrated Megaplan routes. |
| 10 | **HARD FAIL** | Exactly 741 assertions are broadly skipped. Demonstrated live, ancestor-identical subjects remain executable through normal paths, so retirement has manufactured green evidence rather than proving total unreachable/tombstoned behavior. B3-B7. |

## Clause 7 and 8 positive evidence details

The local race/crash implementation has a single occurrence/claim/attempt primary
key and budget ordinal 1 (`arnold/recovery/simple_fixer.py:464-509`), converges
racing claims (`:629-651,691-793`), commits ambiguity before effect (`:840-872`),
and records post-effect claim/authority drift as indeterminate (`:874-932`). The
focused tests cover the two-process immediate/reconcile race at
`tests/cloud/test_simple_fixer.py:170-193`, crash boundaries at `:196-228`,
response loss at `:230-253`, 200 observers and forged sibling files at `:256-274`,
stale leases at `:277-287`, fence change at `:306-319`, and ENOSPC/read corruption
at `:451-465`.

For installed artifacts, entrypoints are declared at `pyproject.toml:58-62`; the
production client uses the fixed socket at `arnold/recovery/simple_fixer.py:314-390`;
owner absence maps to exit 69 at `arnold/recovery/cli.py:94-100`; materialization
copies the two thin wrappers at
`arnold_pipelines/megaplan/cloud/template.py:370-397`; and systemd uses only the
installed canonical names at
`arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.service:11-14`
and `megaplan-progress-audit.service:5-8`.

The independent installed-artifact probe found identical help SHA-256
`1040cee8213a3ae37aa3e1636250249215685fd52265da3901082daf2f8b65d4` for installed
`arnold-simple-fixer`, installed reconcile, installed `arnold simple-fixer`, and
the copied materialized wrapper; installed and materialized mutation entrypoints
both exited 69 with `/run/arnold/recovery-owner-v1.sock` absent. This evidence is
local and disposable, not owner/deployed acceptance.

## External limitations and disposition

- No cloud/provider call, deploy, restart, production socket interaction,
  production owner mutation, git-ref mutation, candidate edit, or checklist edit
  was performed.
- The review did not demand resistance to arbitrary in-process interpreter
  takeover. Every executable blocker used a normal public import, direct module
  execution, or importable internal function specifically inside the frozen
  threat boundary.
- Clause 7 is a local conformance result. It does not establish the correctness
  of an accepted external production owner or deployed race behavior.
- Clause 8 artifact equivalence and owner-absence behavior were independently
  reproduced in disposable local installations. The candidate does not preserve
  that recovery-specific installed evidence in its committed seven-test wheel
  suite.
- No accepted production RA/Custody/WBC owner receipts, installed-release
  receipt, cloud release, authorized fix-the-fixer transaction, independent
  verifier result, or real incident advancement evidence was available or
  created.
- This report makes no formal T1.5 completion claim. The explicit verdict remains
  **HARD FAIL**.
