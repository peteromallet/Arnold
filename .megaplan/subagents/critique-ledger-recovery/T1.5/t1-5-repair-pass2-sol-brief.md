# T1.5 canonical simple_fixer — bounded GPT-5.6 Sol-high repair pass 2

This is 🔥 VERY HARD. Start from exact clean evidence head
`4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a` in
`/private/tmp/arnold-critique-recovery-simple-fixer-20260802`.

Read the independent HARD FAIL report at
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-independent-review-pass1-sol-result.md`,
SHA-256 `9c0a4ebc7afd39466dcb12241d72bf8b994ad1a936cf5b0205bdb39d66f0e1d6`.

Fix the seven reproduced blocker groups only. Do not redesign unrelated cloud
supervision. Do not add arbitrary interpreter-takeover defenses.

## 1. Authority is owner-validated, never caller asserted

- Production owner client and server protocol must bind/authenticate the fixed
  Unix-socket peer, operation, exact occurrence/request digest, response schema,
  owner revision/fence and signed/owner-derived result. A public schema digest
  alone is not peer or response authority.
- Intake must resolve current RA grant, custody target+lease+epoch+fence and WBC
  GLEK from explicit owner ports and compare the F01 subject. Caller mappings or
  caller-constructed `AuthorityEnvelope` cannot mint eligibility.
- Production absence/mismatch/UNKNOWN fails closed. A hermetic conformance source
  must be visibly test-only and use preinstalled owner records, not arbitrary
  strings supplied with the request.
- Remove arbitrary callback/effect execution from the shipped hermetic owner.
  Conformance may record a bounded simulated effect in its own owner store; a
  normal import plus boolean attribute may not write caller-selected files or
  run code.

## 2. Reconcile exact stored result through canonical receipt

- Replay/reconcile must verify result bytes against the canonical receipt,
  occurrence, request/authority/claim/attempt/fence/GLEK, digest and current owner
  record before returning.
- Targeted result/receipt/attempt corruption, deletion, substitution or mismatch
  is typed UNKNOWN/fail-closed, never returned bytes. Preserve response-loss
  no-redispatch behavior.
- Add the exact `FORGED-RESULT` database probe from the report.

## 3. Retire every ordinary legacy execution seam at point of use

- Remove recovery kinds from accepted `AUTOMATIC_RUN_KINDS`, or reject them in
  reservation and the deepest locked executor before any filesystem/process
  mutation. Direct normal import of `_run_managed_command_locked` cannot launch.
- Hard-tombstone `repair_source_initiative`, `repair_goal ensure`/module main,
  `repair_investigation`, and every other subject hidden by the 28 module-wide
  skips. Retire at public, direct-module and imported-internal point of use.
- No old function may create/copy/write workspace, goal, queue, investigation,
  marker, process or repair state. If read-side parsers must remain, isolate them
  from mutation and make all mutators typed unavailable.

## 4. Make fix-the-fixer a genuinely separate owner transaction

- Require owner-derived authorization bound to the exact occurrence/fence,
  canonical SHA-256 implementation/backstop digests, approved target generation,
  durable attempt intent/result/receipt and an independently signed verifier
  decision. Caller labels/strings or verifier-name inequality are not authority.
- Replays are exact; forks or incomplete/missing verification stay UNKNOWN and
  non-actionable. No ordinary fallback or agent launch.
- Dedupe one provenance failure by stable occurrence + typed error code/subject;
  free-form wording is projection only and cannot multiply obligations or quiet
  transitions. Add exact two-detail probe from the report.

## 5. Restore honest coverage and exhaustive inventory

- Remove all 28 module-wide skips / 741 manufactured skips. Preserve meaningful
  historical assertions as retirement negatives or replace each old behavior
  assertion with an explicit typed-rejection/no-side-effect assertion. No blanket
  skip, xfail or collection hiding.
- Build the recovery/effect bypass inventory dynamically from all shipped Arnold
  and Megaplan modules, direct module mains, installed scripts, wrappers, systemd,
  templates and non-Megaplan pipelines. A narrow static JSON is not sufficient.
- Exact regression cases: forged local owner effect; forged stored result;
  internal managed launch; source initiative copy; `repair_goal ensure`; repair
  investigation; caller-minted fix-the-fixer; varying provenance detail; direct
  module/import aliases; installed/materialized owner absence.

## Finite validation

- 22 focused concurrency/crash tests plus new hostile probes;
- full cloud suite with **zero recovery-retirement module skips**;
- RA/custody/WBC/dependency closure;
- installed wheel and materialized wrappers, including recovery owner absence;
- dynamic source/module/script/systemd/container bypass inventory;
- static/compile/shell/diff checks.

Large suites single-flight. Do not touch cloud/provider/production owner state,
git outside this worktree or checklist. Commit scoped code and evidence, leave
clean, and write exact commit/tree/tests/limitations to
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-repair-pass2-sol-result.md`.

No formal T1.5 claim without a new independent Sol-high review and later deployed
owner receipts.
