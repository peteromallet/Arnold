# a01-s02-authority-ownership-critique-revise-gate: authority-ownership × critique-revise-gate

## Verdict

Observed: the surface is not conformant. There is one P0 mutation-ownership split and three P1 authority/evidence gaps, plus P2 status-only bypasses.

- P0 authority mutation: legacy `force-proceed` remains the default reachable path and bypasses CAS-owned custody.
- P1 authority mutation: invalid critique recovery can adopt a pre-existing `critique_output.json` outside the shared transport contract.
- P1 status/control misreporting: `gate_carry.json` is treated as authoritative for revise and finalize policy despite being a projection.
- P1 evidence/control acceptance: custody receipts are called immutable but are overwriteable and are not bound to the current iteration/path.
- P2 status misreporting: feedback prefers scratch critique output over the canonical critique artifact.
- P2 authority metadata mutation: tiebreaker code writes `faults.json` directly outside the flag-owner module.

These are independently evidenced below; no other agent’s conclusions were used.

## Intended canonical contract

The canonical contract should be:

1. Provider output is only a candidate. All providers use `promote_scratch`; inline providers must never inspect scratch, while instructed Hermes file-fill uses only the registered path (`handlers/structured_output.py:123-195`).
2. Critique authority is `critique_v{iteration}.json` plus its custody receipt. The custody layer validates raw evidence, hashes, findings, and registry mapping before gate admission (`orchestration/critique_custody.py:221-303`, `396-428`).
3. `faults.json` is mutated only through `flags.py` phase helpers (`flags.py:279-293`, `311-358`, `373-398`).
4. Gate evidence is produced by the custody-validated gate path (`handlers/gate.py:90-120`); `gate_v{iteration}.json` is immutable evidence and `gate.json`/`gate_carry.json` are projections (`handlers/shared.py:1123-1132`).
5. Workflow mutation is owned by the CAS-backed control interface (`control_interface.py:566-739`). Force-proceed custody in `state.meta` is the authoritative waiver; registry, debt, and gate files are repairable projections (`planning/control_binding.py:1014-1102`, `1659-1681`).

## Evidence and complete path inventory

Search method: `rg --files` enumerated the repository; targeted `rg -n` searches covered `critique`, `revise`, `gate`, `gate_carry`, `critique_output`, `force-proceed`, `save_flag_registry`, custody functions, and all named callers. I separately inspected every production `save_flag_registry` caller and relevant tests.

Writers:

- Critique runtime writes canonical critique and custody artifacts, then updates flags (`orchestration/critique_runtime.py:952-998`).
- Custody writes `critique_custody_vN.json` (`orchestration/critique_custody.py:274-303`) and clearance (`:543-646`).
- Gate writes `gate_carry.json` and `gate.json` (`handlers/gate.py:1171-1174`).
- Force-proceed projection writes `faults.json`, debt, and both gate projections from CAS custody (`orchestration/force_proceed_custody.py:136-223`).
- Legacy force-proceed independently writes `gate.json`, debt, and state (`handlers/override.py:1031-1170`).
- Direct flag-registry writers are `flags.py:233`, `275`, `357`, `398`, `force_proceed_custody.py:174`, and `tiebreaker_runtime.py:362-367`.

Readers/callers/consumers:

- Shared scratch promotion is called by critique and gate (`critique_runtime.py:840-873`; `handlers/gate.py:945-998`).
- Critique recovery directly reads `critique_output.json` (`critique_runtime.py:876-915`, `1065-1078`).
- Gate admission reads custody and flags (`handlers/gate.py:90-120`).
- Revise route policy reads `gate_carry.json` before `gate.json` (`handlers/gate.py:180-218`).
- Revise and finalize North Star guards consume `read_carried_north_star_actions` (`critique_runtime.py:1516-1527`; `handlers/finalize.py:1899-1919`; `north_star_actions.py:600-655`).
- Prompts consume carry projections (`prompts/_shared.py:26-86`; `prompts/critique.py:364-367`).
- Feedback summarizes scratch before canonical critique (`prompts/feedback.py:96-123`).
- Gate signals consume `faults.json` and canonical critique (`orchestration/gate_signals.py:103-160`).

## Adherence gaps

1. **P0 — authority mutation: reachable duplicate force-proceed owner.**

   The canonical route builds custody, performs CAS state mutation, and commits projections afterward (`planning/control_binding.py:646-710`, `1014-1102`, `1659-1681`; `control_interface.py:693-739`). However, `handle_override` routes to that implementation only when `MEGAPLAN_CONTROL_INTERFACE_ROUTING=1`; otherwise `_override_force_proceed` remains reachable (`handlers/override.py:2168-2170`, `1031-1170`). The feature flag is default-off (`feature_flags.py:171-177`; `test_feature_flags.py:261-275`).

   The legacy path mutates gate/state and debt without `force_proceed_custody`, CAS ownership, or projection repair. This is an authority mutation, not merely status misreporting.

2. **P1 — authority mutation: critique recovery bypasses canonical transport.**

   The shared contract explicitly forbids inline workers from adopting scratch (`structured_output.py:184-195`). Nevertheless, after a worker schema/check failure, critique directly reads and validates `critique_output.json`, then promotes it into the current worker result (`critique_runtime.py:876-915`, `1065-1078`). The result is persisted as current critique, custody, and flags (`:952-998`).

   Observed: the fallback has no invocation, provider, seed hash, output-path attestation, or iteration binding. Inference: a valid stale file can replace the current provider result and mutate canonical critique/flag authority. Auto orphan recovery quarantines outputs in one path (`auto.py:3311-3319`, `3327-3345`), but that does not make this direct runtime fallback unreachable.

3. **P1 — status/control misreporting: projection becomes gate authority.**

   `_gate_summary_for_transition` prefers `gate_carry.json` and only falls back to `gate.json` (`handlers/gate.py:180-206`); revise accepts or rejects based on that recommendation (`:209-218`). The carry writer does not include a source hash or pairing proof to `gate.json` (`handlers/gate.py:338-386`). North Star guards likewise prefer carry (`north_star_actions.py:600-655`), and finalize uses the result to block or admit closeout (`handlers/finalize.py:1899-1919`).

   Observed: a projection is accepted after schema validation only. Inference: stale or modified carry can alter revise policy, force-proceed custody inputs, or finalize blocking decisions without changing canonical gate evidence.

4. **P1 — evidence/control acceptance: “immutable” custody is overwriteable and weakly bound.**

   The receipt writer calls the artifact immutable but uses `atomic_write_json`, which replaces an existing same-iteration receipt (`critique_custody.py:221-303`). Validation checks hashes and safe basenames but does not verify that receipt `iteration` equals the filename/current state or that `critique_artifact` is exactly `critique_v{current}` (`:307-393`, `396-406`).

   Observed: the gate derives the expected receipt filename but validates its contents without those bindings. Inference: a copied, correctly self-digested older receipt can be admitted if its referenced artifacts and flags still exist.

5. **P2 — status misreporting: feedback reads non-authoritative scratch first.**

   `_digest_critique` explicitly tries `critique_output.json` before `critique_vN.json` (`prompts/feedback.py:96-123`). This does not directly mutate workflow state, but it can report a stale critique to users or downstream narrative consumers.

6. **P2 — authority metadata mutation: tiebreaker bypasses flag owner.**

   Tiebreaker directly loads, mutates, and saves `faults.json` (`orchestration/tiebreaker_runtime.py:362-367`) instead of using the flag-owned mutation helpers. The field is metadata rather than status, but it creates a second writer for the same authority file.

## Incident reachability and severity

The P0 path is reachable on every default invocation of `override force-proceed`; the existing routing tests prove only the flag behavior and canonical binding, not end-to-end default dispatch (`test_feature_flags.py:261-275`; `test_force_proceed_custody.py:89-210`).

The P1 critique bypass is reachable inside the locked critique handler (`critique_runtime.py:378-387`) whenever provider output fails structural/check validation and a valid scratch file remains. It is provider-sensitive because the shared helper distinguishes Hermes file-fill from inline providers (`structured_output.py:152-195`).

The P1 carry issue reaches revise and finalize policy, not just prompts. The current tests intentionally verify carry preference/fallback (`test_north_star_actions_review_blocking.py:314-325`, `455-465`) but do not test tampering or stale pairing.

## Minimal generalized remediation

- Make the control-interface route unconditional for `force-proceed`. Delete `_override_force_proceed` and remove it from `_OVERRIDE_ACTIONS`; retain only the canonical binding. Update the CLI adapter to call the binding directly. Do not wrap the legacy function.
- Delete `_recover_valid_critique_output` and both callers. Restart recovery must either use the shared, invocation-bound promotion contract or quarantine and rerun. Add an explicit scratch seed/producer invocation hash.
- Add a single verified gate reader. Normal gate decisions must come from `gate_vN.json` plus custody/hash checks; force-proceed decisions must come from CAS `state.meta.force_proceed_custody`. Rebuild `gate.json` and `gate_carry.json`; never use either projection as authority.
- Require receipt filename/iteration/artifact consistency and write receipts create-once under the plan lock. Reject replacement rather than overwrite.
- Move tiebreaker metadata mutation behind a `flags.py` helper.

This is narrower than a rewrite: the canonical custody, immutable gate writer, flag helpers, and CAS binding already exist.

## Required tests and retirement proof

- Default and enabled-provider `force-proceed` dispatch must produce identical CAS custody; assert no legacy handler/mapping remains reachable via AST/source checks and `rg`.
- Two concurrent processes, including separate PID namespaces sharing one plan directory, must yield one CAS winner; the loser must publish no projections. Restart/retry must repair projections idempotently without duplicate debt.
- Mutate `gate_carry.json` recommendation, North Star actions, and transaction ID while leaving `gate_vN.json` unchanged; revise/finalize must use canonical evidence or fail closed.
- Mutate receipt iteration, filename, referenced artifact, and digest; gate must reject. Concurrent receipt creation must not overwrite.
- For Hermes, valid/invalid/missing scratch must follow file-fill rules. For Codex/Shannon, pre-existing valid scratch must be ignored. Provider output-path changes must not be adopted.
- Leave a static retirement test proving zero call sites for `_recover_valid_critique_output`, `_override_force_proceed`, and direct projection-based policy readers.

## Unknowns

- No container integration test was executed during this read-only audit; two-container behavior remains an implementation requirement.
- The external wrapper/CLI entrypoints outside `handle_override` were not proven exhaustively from repository code.
- The available provider invocation identity may not yet be persisted alongside scratch templates; that must be confirmed before implementing restart-safe recovery.