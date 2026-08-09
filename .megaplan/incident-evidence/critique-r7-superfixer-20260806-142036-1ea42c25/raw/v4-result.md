## R7 Superfixer v4 — outcome summary

**Outcome: deterministic root cause found, proven fixed, and the occurrence-preserving repair is mid-execution.** The chain was dead-blocked (not merely slow): no live runner, liveness lease terminal at `2026-08-06T00:53:46Z`, and a reproducible engine defect. The recovery route is **not yet complete** — the finalize retry and cursor-advancement proof remain, stopped only by this run's environment tool budget (not by an external gate).

**Important findings**
- **Blocker reproduced exactly:** `finalize` fails with `critique_finding_unresolved` for findings `CF-0B506E1EDCD92E90C192` and duplicate `CF-B67C1E37D72114DDCF70` — evaluated as `accepted_tradeoff` with a traceable fixed-plan mutation but **no `gate_resolution` envelope**, which the finalize consumer (`critique_custody._resolution_for_finding`) requires. Read-only 95-finding sweep against the live plan data fails on exactly those 2, byte-identical to the chain log.
- **Fix proven:** the 16-line `accepted_tradeoff && gate_expected && fixed_claim → verified_plan_mutation` branch resolves 95/95 findings (verified in two independent pre-existing candidates). Applied it to the pinned runtime as same-lineage descendant commit `9c41d0554` on `fix/r7-fresh-child-launch-20260805`, reinstalled editable, and the focused regression now passes (**95 processed, 0 failures**).
- **Sol adjudications completed:** Sol stage 1 (read-only, high-reasoning) and Sol stage 2 both ran via `codex` GPT-5.6 Sol; stage 2 emitted Horizon A (`repair_control_plane_then_migrate`, `external_gate: null`, `agent_actionable: true`) plus the validated recovery handoff (see below). A canonical follow-up ticket was created.

**Evidence / IDs**
- Occurrence: `occ_critique_r7_superfixer_retry_20260806_v4_14834310cdddb1f2b0eed77e`
- Evidence dir: `/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-130215-69f23ad9/` — `evidence-pack.md`, `repro_finalize_sweep.py`, `sol-stage2.stdout.txt`, `recovery-handoff.json`, `fan-child-custody-receipt.json`, `blocked-receipt.json`
- Handoff ID: `sha256:0e3c1467d6f0b1484168d1bca455171b28f8587754d4d763d6843c4e69599e06`
- Follow-up ticket: `ticket-r7-superfixer-v4-20260806-1329` (Horizon B cross-pipeline hardening)
- Prior evidence incl. full 10-report Flash swarm: `.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5/`

**Fingerprints / models**
- Authoritative before (canonical subset): `sha256:166bbe40c30e800ef036fb60a5abc2f1fab52f2a673948f3680b0ba8498564d5` (byte-identical before/after both Sol passes; only volatile ps/timestamp fields changed)
- Authoritative after: runtime content `sha256:f05c9d81c21c4d58e2d37826f3722d6b9e2872141fc34ba9c45fd7f0492bdcf5` at revision `9c41d0554652756b4fefea1a3b4df6beefb62b0f`
- Observer/executor: `hermes:deepseek:deepseek-v4-flash` (run `subagent-20260806-130215-69f23ad9`); Sol: `codex` `gpt-5.6-sol` high-reasoning; fan: `deepseek:deepseek-v4-flash` (3 read-only investigators interrupted by budget — recorded as not-in-flight)

**Operational caveat (must fix before verifier accepts)**
- The on-disk `blocked-receipt.json` is a **checkpoint**, not completion. It is schema-invalid in one field: `effects.launched` is recorded `true`, but **no chain/runner was launched** — the only effect was the in-scope editable runtime repair. The next actor must regenerate it with `effects.launched: false` (and `mutated: true` retained), then complete Horizon A: `run_mp chain runtime-rebind` (from `e8b12504…` to `f05c9d81…`, milestone `cl2-ledger-replay`, plan `cl2-wbc-backed-ledger-20260805-2140`), then drive the finalize retry through the supported Run Authority→Custody→WBC path and prove canonical cursor/milestone advancement — the precise return condition. Keep the schedule active; this recovery is in flight, not terminal.
