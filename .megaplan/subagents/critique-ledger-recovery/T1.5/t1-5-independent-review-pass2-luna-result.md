# HARD FAIL — T1.5 canonical `simple_fixer` independent review, pass 2

**Verdict: HARD FAIL.**

This is an independent local acceptance verdict for the exact frozen repair
candidate only. It is not a formal T1.5 completion claim, production-owner
acceptance, deployed-runtime acceptance, or evidence that the incident/epic
advanced. The candidate is not eligible for clean-lineage integration in this
reviewed form.

## Frozen identity and evidence admission

- Review worktree:
  `/private/tmp/arnold-critique-recovery-simple-fixer-20260802`
- Repair commit:
  `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec`
- Repair tree:
  `5077ceff4e9ccd8958051acd999fb86172233f8f`
- Exact parent:
  `4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a`
- Commit subject: `fix(recovery): close simple fixer authority blockers`
- Implementer result read from
  `t1-5-repair-pass2-sol-result.md`, independently rehashed SHA-256
  `ada2fbcd0e963cd8a658fca1df9ff5359710cdf1c95433195af147cb5e98740c`.
- Pass-1 report and pass-2 brief were reread before review.

Admission and final rechecks used `git status --porcelain=v2 --branch
--untracked-files=all`, `git rev-parse HEAD HEAD^{tree}`, and `git diff --check
4bfd5fb2..HEAD`. The candidate worktree remained clean at the exact commit/tree;
the diff check was clean. Review probes used disposable temporary directories
only. No candidate source, Git ref, cloud/provider state, production owner,
checklist, or deployed runtime was mutated.

## Fresh targeted validation

The implementer's focused command was independently rerun, without a broad
wheel build or cloud suite:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/cloud/test_simple_fixer.py \
  tests/cloud/test_simple_fixer_retirement.py \
  tests/cloud/test_progress_auditor.py \
  tests/cloud/test_repair_delegation.py \
  tests/cloud/test_wrapper_authority_bypass_gating.py \
  tests/m9/test_bypass_gating.py \
  tests/resident/test_fix_the_fixer_command.py \
  tests/test_managed_agent.py \
  tests/arnold_pipelines/megaplan/watchdog/test_repair_runner.py
112 passed in 13.11s
```

Green committed tests were treated as observations, not as proof against new
hostile cases.

## Remaining blockers

### B1 — coordinated stored-result and receipt substitution still replays forged bytes

`TestOnlyHermeticRecoveryOwner._stored_result()` parses the stored result and
receipt and recomputes the receipt digest, but it validates only selected result
keys with `.get()` (`arnold/recovery/simple_fixer.py:964-1054`, especially
`:1037-1043`). It does not require the exact canonical result object that the
owner emitted, nor reconstruct and compare the result from the durable simulated
effect. The receipt is unkeyed data in the same row, so changing the result and
its receipt digest together passes reconciliation.

A fresh disposable probe performed one valid owner run, added an
attacker-controlled field to `attempts.result_bytes`, updated only the
`result_digest` in `attempts.receipt_bytes`, and called the ordinary reconciler
path again. It did not modify occurrence, claim, attempt identity, authority,
owner record, WBC GLEK, state, or the effect record. Observed output:

```json
{"effect_count":1,"forged_projection":"attacker-controlled","original_equal_replay":false,"replayed_bytes_sha256":"18f35c0bab08a49ac46f8b3708f83ed24a9d9e38d79d0f8e2faa8568046ccb00"}
```

The forged bytes were returned rather than typed
`RESULT_RECONCILIATION_UNKNOWN`. The checked-in exact `FORGED-RESULT` case
changes result bytes alone, and the parametrized corruption cases change one
column/record at a time; none exercises coordinated canonical result/receipt
substitution. This fails the pass-2 requirement that substituted result/receipt
data be canonical, exact, and fail closed.

### B2 — dynamic inventory misses a normal imported Megaplan repair launcher

`build_bypass_inventory()` discovers Python files, but `_python_entry()` treats
an unlisted Megaplan module as `observational_or_unrelated_module` even when it
is recovery-relevant and has effect functions. For such modules, a violation is
only produced for a direct `__main__` whose *main body itself* matches the narrow
legacy regex (`arnold/recovery/bypass_inventory.py:128-220`). Imported functions
and transitive aliases are not rejected.

A fresh hostile fixture added this ordinary shipped-shaped module under the
scanner root:

```python
import subprocess

def launch_repair():
    return subprocess.Popen(['/usr/local/bin/arnold-repair-loop'])
```

at
`arnold_pipelines/megaplan/cloud/ordinary_repair_alias.py`. The dynamic scanner
reported:

```json
{
  "direct_module_main": false,
  "disposition": "observational_or_unrelated_module",
  "effect_functions": ["launch_repair"],
  "recovery_relevant": true,
  "violations": []
}
```

The top-level inventory also had `"violations": []`. This is exactly a normal
imported repair-launch alias without the fixed owner, so the inventory is not an
exhaustive bypass gate. The committed hostile inventory test covers a
non-Megaplan module and a Megaplan *direct main*, but not this ordinary imported
Megaplan seam.

### B3 — 741 historical cases are collected, but their assertions were erased rather than restored as meaningful negatives

The 28 formerly skipped modules do have no blanket skip/xfail and collect 741
case IDs. However, every one of their 674 test functions now has exactly one
statement: a call to
`assert_historical_recovery_case_retired(__name__, <test-name>)`. An independent
AST count found:

```text
{'modules': 28, 'test_functions': 674, 'helper_only_test_functions': 674}
741 tests collected in 0.50s
```

The repair diff over those 28 files is 2,105 insertions and 27,344 deletions.
The shared helper routes all 741 cases to a few module-level generic checks
(`tests/cloud/recovery_retirement_contract.py:61-219`): queue, goal,
investigation, source copy, trigger source text, or one wrapper selected mostly
by module/test-name substring. It does not preserve or replace each historical
behavior assertion with a corresponding typed rejection/no-side-effect probe.
For example, all 24 distinct `test_repair_goal.py` cases exercise the same call
to `ensure_repair_goal`; all 30 repair-trigger cases merely inspect one wrapper
source string; and hundreds of wrapper-policy/custody/runtime cases collapse to
executing one selected tombstone with a generic argument.

This is collection-count preservation, not restoration of meaningful historical
coverage. It violates the explicit pass-2 instruction to preserve meaningful
historical assertions as retirement negatives or replace each old behavior
assertion with an explicit corresponding rejection/no-side-effect assertion.
It also leaves the scanner weakness above without honest regression coverage.

## Seven-group pass-1 blocker audit

| Prior blocker group | Pass-2 finding |
|---|---|
| B1 caller-minted authority/local callback effect | **Repaired in bounded source scope.** Production adapters construct only the fixed owner client; caller authority is rejected. The production socket path/type/UID and connected peer are checked, and request/response identity is bound. The hermetic owner is visibly test-only, direct construction fails, records must be preinstalled typed records, and the arbitrary effect callback seam is gone. Public export of the test-only classes is not by itself a production bypass because no production adapter accepts the test owner and its only effect is a row in its own test store. |
| B2 forged stored result replay | **Still HARD FAIL.** Single-column corruption is rejected, but coordinated result/receipt substitution returns forged bytes. Remaining blocker B1 above. |
| B3 managed child/internal executor | **Repaired.** `AUTOMATIC_RUN_KINDS` contains only `automatic_research_subagent`; reservation, public execution, deepest imported locked execution, and manifest validation reject every retired recovery run kind before mutation. Fresh targeted tests passed. |
| B4 source initiative copy | **Repaired.** Public and imported copy/overlay seams raise before filesystem work. Fresh targeted tests passed. |
| B5 repair goal/investigation/queue/direct-module seams | **Repaired for the specifically audited mutators.** Goal, investigation, and queue mutators reject at point of use; goal/investigation mains exit 78 before parsing or writes. Fresh targeted tests passed. The dynamic gate meant to prove future/alias completeness is still unsound (remaining blocker B2 above). |
| B6 fix-the-fixer/provenance dedupe | **Repaired in the hermetic protocol model.** Caller authority is forbidden; the owner-preinstalled typed authorization binds occurrence/fence, canonical SHA-256 digests, generation, verifier signature, and durable exact intent/result/receipt. Consumed/missing/corrupt transactions fail closed. Dedupe excludes free-form detail. Fresh targeted tests passed. No deployed independent verifier or production transaction was available. |
| B7 honest coverage/exhaustive inventory | **Still HARD FAIL.** The scanner misses an ordinary imported Megaplan launcher, and the 741 collected IDs are generic helper repetitions after erasing their historical assertions. Remaining blockers B2-B3 above. |

## Disposition and limitations

The repair closes most live pass-1 execution seams and the focused concurrency,
crash, authority, retirement, and fix-the-fixer tests are green. That does not
cure exact stored-result forgery or prove exhaustive retirement. Because the
hostile probes reproduce both a forged replay and an inventory false negative,
and because the required historical coverage was collapsed rather than restored,
the only defensible independent verdict is **HARD FAIL**.

No production owner/socket was contacted, so this review does not validate an
external owner implementation, deployed peer credentials, signed deployed
receipts, an installed release, an authorized production fix-the-fixer
transaction, or real incident advancement.
