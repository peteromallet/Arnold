# Maintenance runtime consolidation — execution log

- Plan: `docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md`
- Integration base: `fce48030a82d4d35d9b4a5184e4c789792b9c172`
- Remote integration target: `origin/fixer/runtime-convergence-r` (push explicitly `HEAD:fixer/runtime-convergence-r`)
- Integration worktree: `~/Documents/.megaplan-worktrees/runtime-convergence-execution`
- Launcher root (absolute): `/Users/peteromalley/Documents/.megaplan-worktrees/runtime-convergence-execution/arnold_pipelines/megaplan/skills/subagent-launcher/`
- Cloud: `root@159.69.51.216`, container `megaplan-cloud-agent-resident-only`, project `/workspace/megaplan-maintenance/Arnold`
- Candidates: `/workspace/runtime-candidates/astrid-first`, `/workspace/runtime-candidates/arnold-4a830c6ac9a0`
- Machine-readable authority: `docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json`

## Pre-T0.0 orchestrator environment record

- Integration remote ref observed (read-only `git ls-remote`): `origin/fixer/runtime-convergence-r` = `a610c220da202c6c4a45c4c990ebef4be9f53942`
- Integration worktree HEAD: `a610c220da202c6c4a45c4c990ebef4be9f53942` on `integration/goal-maintenance-runtime-20260820`, clean
- `fce48030a82d4d35d9b4a5184e4c789792b9c172` resolves locally and is ancestor of integration HEAD
- Milestone tips local presence at pre-T0.0: M1 `67e7b94a…` present, M2 `15b881cb…` present; M3 `58d4a935…`, M3b `7272cdc7…`, M4 `759e3186…`, M5 `800fa276…` MISSING locally (cloud fetch required at T0.1)
- Launcher availability: `launch_omp_agent.py --model grok-4.6 --dry-run` resolves to `omp -p --model grok-4.6 --no-session`; `omp` binary at `~/.bun/bin/omp`
- Cloud reachability: SSH `root@159.69.51.216` OK; container `megaplan-cloud-agent-resident-only` running

## Card log

(append per card/gate)

## T0.0 — capture immutable live-state baseline — PASS

- Disposition: complete. 47 evidence artifacts under `docs/arnold/maintenance-runtime-consolidation-evidence/baseline/T0.0/`; `baseline.json` digest `f5dfdf50bf3c552d24a53b0027b05123228135cc5473fdf1ddd5d842d2b4149b`; zero digest mismatches.
- Input SHA: n/a (read-only). Output: baseline evidence pack (no code, no commit).
- Model: GPT-5.6 Luna (`codex:gpt-5.6-luna` → resolved `openai-codex/gpt-5.6-luna`). Direct bootstrap launcher call (pre-T0.3 wrapper): `launch_hermes_agent.py --model=codex:gpt-5.6-luna --query-file=<brief> --project-dir=<INTEGRATION_WORKTREE> --metadata-file=<runroot>/metadata/T0.0-impl.metadata.json --toolsets=file,web,terminal --timeout=3600`. Launcher PID captured in metadata receipt; exit 0; elapsed 673.86s.
- Brief: `mrc-run-20260820/briefs/T0.0-brief.md` digest `dddfb97e3e810254ab06afdc56dfadf47aa7a19e29d43180b62b873ea572dc1b` (authored by Luna brief-prep subagent, invocation T0.0-prep).
- stdout digest `6a6f636e…`, stderr digest `bab54e81…`; metadata receipt `metadata/T0.0-impl.metadata.json`.
- Key observed state: integration HEAD `a610c220da…`; candidates astrid-first HEAD `423ec212c6…`, arnold-4a830c6ac9a0 HEAD `be709be7db…`; final reconcile plan `reconcile-outcome-select-and-20260819-1828` state `done` iteration 8, artifacts captured unchanged, disposition observed only (no write), process identity unknown/absent, repo SHA unknown; requested path `arnold-4a830c6ac9` unavailable, actual `arnold-4a830c6ac9a0` captured (no silent substitution).
- No mutation: no git writes, no process actions, no cloud/candidate/plan/chain/selector/ledger writes, no tests run.
- Next: T0.1 preserve milestone objects.


## INPUT-BOUNDARY CONFLICT RECORD (between T0.1 and G0)

- Observation: during the T0.1 implementer run (mtimes 2026-08-20 16:40:38 / 16:42:22), the frozen input boundary was mutated in the integration worktree working tree (UNCOMMITTED):
  - `docs/arnold/maintenance-runtime-consolidation-execution-plan-2026-08-20.md` gained a `T4.4 [XHARD]` card ("Atomic runtime identity vector and single occurrence mutation owner") plus `G4.4-pre`/`G4.4-post` gates and a "Batch 5 blocked until T4.4 passes" note (11 T4.4 mentions).
  - `docs/goal-execute-maintenance-runtime-consolidation.md` gained matching T4.4/G4.4 outcome criteria (7 T4.4 mentions).
- Committed integration HEAD `a610c220da` plan/goal contain ZERO T4.4 mentions; `git log --all -S "T4.4" -- <plan>` finds no commit on any branch — the revision is working-tree-only.
- T0.1 implementer (Luna) reported it ran an off-script "Megaplan initialization" that failed (`runtime_launch_attestation_mismatch`), left disposable worktree `runtime-convergence-t0-1` with the same uncommitted doc modifications, and then stopped at the integration boundary rather than committing the T0.1 manifest. The custody objective (six objects + safety refs) was completed and verified independently of this.
- Goal attachment (authoritative user input) enumerates the required sequence with NO T4.4 and says: if goal and plan appear to disagree, preserve the plan's safety constraint and model-routing rule, record the conflict, and resolve it before mutation. Source-identity-change rule: retain both observations, classify the later state separately, do not silently move the frozen input boundary.
- Disposition: routed as a material input-boundary judgment to a fresh Grok 4.6 judgment subagent (label `[XHARD-REVIEW]`). Both variants preserved under `mrc-run-20260820/evidence-input-boundary-change/` (plan/goal WORKING-TREE + HEAD-COMMITTED + diffs; digests recorded).
- Pending T0.1 completion: evidence manifest commit (blocked pending boundary resolution); cleanup of stray worktrees `runtime-convergence-t0-1` / `runtime-convergence-t0-1-clean` after resolution.


## J1 — material judgment: input-boundary mutation — PASS (recommendation A)

- Question: adopt the uncommitted working-tree T4.4/G4.4 revision (option B), freeze at committed HEAD a610c220da (option A), or hybrid (C)?
- Grok 4.6 judgment (fresh, role judgment, label [XHARD-REVIEW]): RECOMMENDATION A — frozen committed boundary. T4.4/G4.4 observed-only; T0.1 RE-BRIEF; capture-then-remove stray worktrees; Batch 4 = T4.1→G4.3; Batch 5 = T5.1 after G4.3, not blocked by T4.4.
- Launcher: launch_omp_agent.py --model grok-4.6 --query-file=<J1 brief> --project-dir=<INTEGRATION_WORKTREE> --timeout=3600 (pre-T0.3 bootstrap direct call). stdout 54c16a52…, stderr 97ee9ea8…, exit 0, elapsed 537.18s. omp child PID not instrumented pre-wrapper (noted).
- Judgment brief: mrc-run-20260820/briefs/J1-input-boundary-judgment-brief.md digest 3bc77a1f…
- Luna evidence subagent recorded receipt: docs/arnold/maintenance-runtime-consolidation-evidence/adjudications/J1-grok-judgment.json digest 8a43b988… (invocation J1-record).
- Rejected: B (adopt T4.4), C (hybrid), MECHANICAL-MANIFEST-COMMIT-RERUN (no manifest exists), preserve/quarantine/silent-reuse of stray worktrees.

## R1 — boundary restoration per J1 — PASS

- Luna implementer (invocation R1-impl) restored integration plan+goal byte-for-byte to committed HEAD (digests d94bef32… / 54c0fac8…; surgical `git checkout HEAD --`), captured both stray worktrees (48-file inventory, sole unique artifact = older exec log 4fd0209b…; clean failed-init plan/epic trees copied completely incl. state.json/phase_result.json/events.ndjson), captured later-dirty integration docs (plan 1e68a278…, goal ec341445…) as classified-later, wrote capture receipt (e504e071…) + restoration receipt (0d04878f…), removed both stray worktrees (--force only after receipts).
- Post-state: integration worktree clean except untracked docs/arnold/maintenance-runtime-consolidation-evidence/ and execution-log. No commit made.
- Next: T0.1 RE-BRIEF (fresh Luna brief + fresh disposable worktree + fresh Luna implementation; forbid megaplan init; verify six objects + safety refs; author+commit refs-manifest.json only).


## T0.1 RE-BRIEF (per J1) — PASS

- Fresh Luna brief-prep (T0.1-rebrief-prep, digest 784f1d8f…) → fresh Luna implementer (T0.1-rebrief-impl, direct bootstrap call, exit 0, 448.49s).
- Verify (no refetch): all six tips `git cat-file -e <sha>^{commit}` exit 0; six safety refs match exact tips via `git show-ref`; merge-bases vs fce = 4a830c6ac9a0… re-recorded.
- Authored `docs/arnold/maintenance-runtime-consolidation-evidence/milestones/T0.1/refs-manifest.json` (2255 lines; digest 60a2de9c…) with canonicalization, command records, component digests, milestones, object-reachability checks, merge-base checks, pack-transfer historical evidence (f5e2ce1c…), ref snapshot, lifecycle, integration state.
- ONE evidence commit: `502a641f0e evidence(T0.1): preserve milestone custody manifest` on integration/goal-maintenance-runtime-20260820; `git show --stat` = exactly the manifest file (2255 insertions). Parent a610c220da.
- Receipt anomaly recorded: implementer stdout was malformed (2-line summary referencing a missing prior narrative); completion was verified by repo state, not the narrative. Residual: strict commit timestamp not instrumented (noted in manifest lifecycle).
- No push; remote origin/fixer/runtime-convergence-r still a610c220da. Live/cloud/selector/candidate state untouched.
- Leftover disposable worktree `runtime-convergence-t0-1-rebrief-20260820-1528` (detached HEAD a610c220da) queued for removal on next Luna workspace-prep card.
- Next: T0.2 source selection manifest.


## T0.2 — source selection manifest — PASS

- Luna brief-prep (digest 8b81492a…) → Luna implementer (T0.2-impl, direct bootstrap call, exit 0, 1174.31s).
- Output: `docs/arnold/maintenance-runtime-consolidation-evidence/selection/T0.2/source-selection-manifest.json` (536,939 B; digest 46c1ce89…). Canonical JSON verified; T4.4 material absent; worktree mutation limited to the manifest path.
- Inventory: 26 unique commits across M1–M5; 212 selected/adapted behavior hunks; 16 cards bound T1.1–T6.3; per-milestone classification counts recorded (keep/adapt/superseded/generated-evidence/evidence-config-only).
- Seed resolutions: T1.1 `fa42ff979f69c44183303d76e76f7e6b7b12465c`; T3.1 `3a94a1f54492292ac1bb5fbdad0db4c7eaadb73e` (EXTERNAL seed — custody gap flagged); T4.1 `9056775d6c4bd24823ee974fd7da198eeadedf92`; T5.1 `62d3cae7fb7a873a00eaf87a9db52ff1921e7605`.
- Seam bindings recorded: T2.1 sole claim authority (resident/schedules.py: ScheduleService.claim / claim_superfixer_occurrence, CAS fence/claim_token/claim_expires_at); T4.3 selector/marker/manifest/lease/fence/rollback paths + 4 CAS owners; T6.1 M5 `emit_daily_events` + canonical writer IncidentLedger.append_maintenance_event; T6.2 `run_daily_efficiency` + derive_daily_closure + typed non-appending outcomes; production rejects fence_check=None and always-never-seen prior-key.
- 8 G0 questions routed to Grok 4.6 (external T3.1 seed admissibility, M3–M5 pack provenance, mixed-commit equivalence, T4.3 CAS ordering, T2.1 sole authority, T6.1 single writer, T6.2 fallback rejection, M5 ticket-policy exclusion).
- Next: T0.3 evidence schema/validator/wrapper (Luna bootstrap).


## T0.3 first-use finding F-001 (wrapper defect) — routing [HARD-REVISION]

- Finding: first real wrapper dispatch (INT-batch0-prep, invocation mrc-54a1d683…) closed `failed` (exit 78) even though the launcher child exited 0 and produced the brief. Cause: launcher emits `resolved=openai-codex/gpt-5.6-luna` on STDERR; wrapper `_resolved_model()` scans STDOUT only → `resolved_model: unknown` → receipt closed failed. Affects every Luna (and likely Grok) dispatch; wrapper is the mandatory post-T0.3 dispatch path. MUST severity (blocks all wrapper-based work).
- The agent work itself completed correctly: brief `mrc-run-20260820/briefs/INT-batch0-brief.md` digest 9ac774c433be96a9b452211b67a548445d718483b6220ba65e12d24d1fe565f3; allowance `allowances/INT-batch0.json` digest e020ec01488d00672150df9df317a62dc9f47c64e58e783e6253ffa32b747842. These artifacts remain usable after the fix.
- Classification: [HARD-REVISION] — confined to `scripts/run_maintenance_consolidation_agent.py` (resolved-model extraction), governing contract frozen (T0.3 acceptance: "captures ... resolved model from launcher output"), changes no authority/custody/identity/migration/concurrency/replay/compatibility/public-schema/live-runtime/task-scope/policy dimension. Not ambiguous → no Grok classification judgment required.
- Required fix: parse resolved model from launcher stderr as well as stdout (or the launcher's `resolved=` diagnostic); add a counterexample test (mock launcher emitting resolved= on stderr → receipt closes completed with parsed model).
- Route: fresh Luna brief-prep → fresh Luna [HARD-REVISION] implementer → fresh independent Luna [HARD-REVIEW] re-review of complete wrapper diff → integration of revision commit (extends INT-batch0 card) → re-dispatch INT-batch0 integration with the already-authored brief.


## OPERATOR VERDICT (user interjection, 2026-08-20, supersedes conflicting inputs) — Live Tree Authority

Context: astrid-first blocked ~1h+ on runtime split-brain: seed 98 pins 423ec212c, manifest gen 99 pins e6ef9f0fb, candidate HEAD 5331e02e3 (same import_root, three SHAs). Rebind gate refused: "runtime provenance receipt is stale or forged" (execution_binding.py:766). Two superfixer runs failed to recover.

Verdict (user): Live Tree Authority wins. Current authority = the live tree at epic.runtime_root (+ its generation interpreter). Git SHA is an observation on accepted work, not a launch pin; compatibility is import_root + per-artifact schema fields, not a new SHA/epoch pin. The five-component vector is "five copies of a pin that should not be a pin." Engine self-contradiction cited: runtime_attestation.py:1290 (engine change on same import_root is a NON-EVENT) vs :1145 (gates live_head == expected_revision) and execution_binding.py:758 (byte-equal receipts); advance_generation / arnold-promote never call ensure_runtime_launch_seed (designed hole, not missed atomic write).

Directives for consolidation:
1. Reject SD-011 five-component CAS-converged vector. T4.4 keeps the T2.1 occurrence-owner freeze but DROPS seed + preflight-SHA components. Sole rebind CAS = import_root (+ generation interpreter). Update the G0 freeze contract accordingly. Do NOT classify seed/preflight as "already present at fce" — they are the failure, not the authority.
2. DELETE as gates (KEEP as evidence): seed store, dispatch-current.json, MEGAPLAN_RUNTIME_LAUNCH_SEED requirement, receipt byte-equality for same-root, runtime_vector_sha256 admission, babysitter manifest→marker→chain→seed ceremony. KEEP: manifest as tree selector, mixed-module / foreign-.pth / interpreter checks, spec/asset CAS, append-only process stamps, expected_head as telemetry.
3. Live split box (NOT consolidation, same seam): do NOT reset candidate to e6ef9f0fb (destroys run-2 fix 5331e02e3); do NOT advance_generation to 5331e02e3 as "recovery". After wall-removal lands, recovery is ONE command: `ARNOLD_RUNTIME_MANIFEST=/workspace/.megaplan/astrid-first.json python3 -P -m arnold_pipelines.megaplan chain start --one`.
4. Adjudicator caveats: keep dependency_generation.interpreter_path as a launch check (interpreter identity ≠ SHA); do NOT introduce a STATE_SCHEMA_EPOCH launch pin (per-artifact schema fields already fence incompatible state).
- User offered: route a fresh Grok review of the G0 freeze once drafted.
- Orchestrator routing decision: after the in-flight G0 selection adjudication (G0-grok) lands, dispatch a FRESH Grok 4.6 judgment (role JUDGMENT, label [XHARD-REVIEW]) on the amended G0 freeze (Live Tree Authority contract), then a Luna evidence agent records the receipt; the amended freeze binds T4.1/T4.2/T4.3 (and any T4.4 scope) before those cards start.


## G0 — custody and selection gate — PASS (after FAIL→J2→revision cycle)

- G0 Luna inventory (mrc-17129211…): mechanical coverage PASS, adjudication_performed=false.
- Original Grok adjudication (G0-grok, mrc-3fdeb5df…): FAIL, 5 must findings (MF-001 external T3.1 seed custody; MF-002 7272 cutover hunks selected on T4.1/T4.3; MF-003 second claim API on 759/800; MF-004 T6.2 unsafe fallbacks; MF-005 false already-at-fce on 67e/f579) + 5 should findings. Receipt: gates/G0/G0-grok-judgment.json (562a1b47…).
- Operator verdict (user): Live Tree Authority — live tree at epic.runtime_root + generation interpreter is authority; Git SHA is observation not launch pin; compatibility = import_root + per-artifact schema; sole rebind CAS = import_root + interpreter; delete seed store / dispatch-current.json / MEGAPLAN_RUNTIME_LAUNCH_SEED / receipt byte-equality / runtime_vector_sha256 / babysitter ceremony as gates (keep as evidence); keep manifest as tree selector, mixed-module/.pth/interpreter checks, spec/asset CAS, append-only stamps, expected_head telemetry; no STATE_SCHEMA_EPOCH.
- J2 Grok judgment (mrc-1f420539…): AMEND — freeze reconciled; T4.4 has NO surviving scope (occurrence-owner freeze fully in T2.1/G0-005/MF-003/T4.1-T4.3); G0 remains FAIL until revision. Receipt: adjudications/J2-amended-freeze-grok-judgment.json (727196ce…).
- T0.2 revision (HARD-REVISION, mrc-cf8fd69f…): MF-001..005 + SF-002 applied; manifest digest e087a70a… (532,372 B). Commit cefd55aa69.
- T0.1 additive seed custody (HARD, mrc-00ed35d3…): refs/heads/safety/maintenance-t3.1-external-seed → 3a94a1f54492292ac1bb5fbdad0db4c7eaadb73e; record milestones/T0.1/seed-custody-T3.1.json ("provenance evidence, not launch authority"); six existing refs untouched. Commit a6eb0eae95 (integrated via cherry-pick).
- Evidence integration (INT-g0rev, mrc-54c71b39…): commit f25d9be90d (G0 inventory + G0 judgment + J2 judgment + log), cherry-pick a6eb0eae95. HEAD a6eb0eae9554504d0cb98a3ab83ac9f1c0e6518a.
- FRESH Grok 4.6 re-review (G0-rereview, mrc-9f978205…): **PASS** — all MF-001..005 + J2 launch-seed amendment verified against revised T0.2 + seed custody; must_findings=[]; should-residuals are hygiene/evidence-text lag only; J1 sequence preserved (Batch 4 = T4.1→G4.1→T4.2→G4.2→T4.3→G4.3; Batch 5 = T5.1 after G4.3; no T4.4/G4.4); Live Tree Authority freeze binding with zero authority drift.
- G0 disposition: PASS. Batch 1 may start under the J2 freeze. Next: record receipt → commit batch-0 evidence + push → T1.1/T1.2/T1.3.


## F-002 — LIVE SECRET in committed T0.0 baseline; push blocked (material judgment)

- GitHub push protection rejected `git push origin HEAD:fixer/runtime-convergence-r` (batch-0 closeout, INT-b0push, mrc-47667cce…). Remote still a610c220da. Dry-run push passes at protocol level (server-side secret scanning only runs on real object upload).
- Cause: `docs/arnold/maintenance-runtime-consolidation-evidence/baseline/T0.0/raw-cloud-container.txt` (committed at b14c727e29 as part of T0.0 baseline) contains a live OpenAI-format API key `<REDACTED-OPENAI-KEY>` captured from the cloud container env via docker inspect.
- Inventory: exact-file scan of all committed evidence under docs/arnold/maintenance-runtime-consolidation-evidence/ finds ONLY this file. No other secret-like content.
- Conflict: T0.0 baseline is contractually immutable/content-addressed (T7.4 compares against it; SF-004 unknowns stay unknown); a live secret cannot be pushed to GitHub.
- Material judgment required: how to reconcile baseline immutability with pushability (redact-and-audit vs. exclude vs. other), plus rotation recommendation for the exposed key (it never reached GitHub, but was written to local git objects in plaintext).
- Routed: fresh Grok 4.6 judgment (J3) via wrapper. Batch-0 push stays blocked pending ruling.

