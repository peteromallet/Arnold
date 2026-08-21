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


## R002 HARD-REVIEW — NOT PASS (4 must findings) → R002-REV2 routing

- Reviewer: independent Luna (mrc-70a0f9b2…, 1055.77s). Single-field redaction + index/manifest consistency + authority records PASS at c92eabc710 evidence state; reachable-graph scan clean; validator passes.
- R002-001 (must, HARD-REVISION): F-002-redaction-receipt.json final_hygiene_commit_sha is null; J3 requires non-null = c92eabc71046608b626cccc90a74e46da47101ef.
- R002-002 (must, HARD-REVISION): rewrite changed pre-boundary ancestry — old parent 9d3efebe08… not ancestor of HEAD; rewritten parent 083e66eaa9… is. Receipt map omits pre-b14c727e29 rewritten objects. Fix: document complete rewrite scope (full old→new map incl. pre-boundary) + prove pre-boundary commits' trees byte-identical (blob-level equality), record as bounded revision.
- R002-003 (must): expected review tip c92eabc710…; actual HEAD b26f3f5778… (PLANAMEND landed after).
- R002-004 (must): b26f3f5778 changes plan/goal docs (2 paths, 126+/9-) — outside F-002 allowed surface.
- R002-003/004 disposition: NOT a defect — the tip change is the OPERATOR-DIRECTED plan amendment (directive recorded in this log; PLANAMEND card mrc-1fcd861d…, commit b26f3f5778 "Amend maintenance consolidation execution plan"). J1 froze the boundary against UNCONTROLLED mutation; this is a controlled operator-authorized boundary amendment (T2.4 insertion + incident table + goal Batch-2 line). Evidence note will cite the directive + amendment commit so the re-review accepts the true tip.
- Route: bounded Luna [HARD-REVISION] (R002-REV2): fix receipt final SHA (R002-001); complete rewrite map + pre-boundary blob-equality proof (R002-002); add operator-amendment evidence note resolving R002-003/004; then FRESH independent re-review at the true tip b26f3f5778.
- Push stays blocked until re-review PASS.


## F-003 — wrapper has no allowance-close path (registry deadlock)

- Finding: scripts/run_maintenance_consolidation_agent.py reads the allowance registry from manifest.json (reject_allowance_overlap) but has NO subcommand/flag to deactivate a completed task's allowance record. The R002-resume implementer registered its own allowance (allowance_id R002-resume, task_id F-002, active:true) in manifest.json as part of its manifest updates. Every subsequent wrapper dispatch whose allowance overlaps that record's paths — including the mechanical deactivation card and R002-REV2 — is rejected with OVERLAPPING_ALLOWANCE. Self-deadlock.
- Severity: must (blocks all further evidence-path dispatch until resolved).
- Classification: [HARD-REVISION] — single production file (scripts/run_maintenance_consolidation_agent.py) + its test; governing contract frozen (T0.3 requires a per-task atomic allowance registry and overlap rejection; lifecycle closure is implied); changes no authority/custody/identity/migration/concurrency/compat/live-runtime/task-scope/policy dimension. Not ambiguous → no Grok classification judgment required.
- Required fix: add a wrapper subcommand/flag (e.g. --deactivate-allowance <allowance_id>) that atomically marks the named registry record active:false + lifecycle_state:closed (+ closed_at_utc) in manifest.json; add a focused test; keep overlap rejection intact for active records.
- Route: Luna brief-prep → Luna [HARD-REVISION] implementer (allowance = wrapper source + test only, disjoint from the stale R002-resume record so the wrapper accepts dispatch) → independent Luna [HARD-REVIEW] → integration; then use the new close path on R002-resume, then re-dispatch R002-REV2.


## R003 HARD-REVIEW — findings (F-R003-001) → R003-REV2

- Reviewer: independent Luna (mrc-8d923452…). Contract table: all Pass except byte-preservation.
- F-R003-001 (must, HARD-REVISION): --deactivate-allowance serializes the whole manifest via json.dump (normalizes formatting, unicode escapes, key order, trailing content). Narrow fix: lossless source-preserving update that changes ONLY the target record's active/lifecycle_state/closed_at_utc; add successful-close byte-level regression test with noncanonical JSON.
- Route: Luna [HARD-REVISION] (R003-REV2) → independent re-review → then use --deactivate-allowance on R002-resume → then R002-REV2 → re-review → push.


## OPERATOR DIRECTIVE (2026-08-20) — review cadence relaxation (supersedes per-card review policy)

- User directive: "do only one review for each subsection and then one up to 3 big ones at the end based on sol".
- Interpretation (recorded, default-to-action): replace the per-card pre/post XHARD review chain (G4.1/4.2/4.3 pre+post, G5 pre+post, G6.1/6.2 pre+post, G7.4-pre/post as separate per-card gates) with ONE review per subsection (the existing batch gates G1/G2/G3/G4/G5/G6.3, each covering its whole batch), and consolidate the whole-system reviews (G3.5 midpoint, G6.4 systemic, G7 final) into UP TO THREE big end-stage reviews based on Sol (`codex:gpt-5.6-sol`, high-reasoning route, fresh instance each, read-only):
  1. Whole-system architecture/authority/simplification attack (covers G3.5+G6.4 concerns: observation→effect paths, duplicated authority, over-enforcement, dead-PID dual, false-success fixer, Live Tree Authority adherence);
  2. Evidence manifest + selection completeness + validator integrity (covers T7.1/T7.5 closure concerns);
  3. Final promotion recommendation (covers G7; after validator passes, before promotion decision).
- Preserved safety rails: must-findings still block; reviewer never reviews its own work; reviews read-only; findings still get evidence-linked revision cards with independent re-review; material judgments still Grok/Judgment-routed; T2.1 sole claim seam unchanged.
- Cadence now: implement (Luna ordinary / Grok XHARD per routing) → ONE subsection review → continue; end-stage: up to 3 Sol reviews → promotion recommendation.
- Wrapper impact: needs a `gpt-5.6-sol` model route (hermes launcher --model=codex:gpt-5.6-sol) for the big reviews; add via a bounded wrapper revision (R004) after R003-REV2 lands (serialization on the wrapper file).
- Plan doc: review-ownership table + per-card review text updated by a routed plan-amendment card (folded into the J4 prep flow).


## R003-REV2 first dispatch — HOLLOW RECEIPT, mechanically rejected

- Invocation mrc-f278d0e0… closed completed/exit 0 but stdout = single byte "1"; no commit created, no worktree/branch left, no wrapper change, test count still 13. No deliverable exists.
- Disposition: mechanical receipt rejection (not a judgment); re-dispatch R003-REV2 with the same brief.


## F-R003-002 — close path leaves stale allowance_digest (validator DIGEST_MISMATCH)

- Finding (from canonical validator run at commit 6f3739823e): allowances[0] (R002-resume, closed) has allowance_digest cc26ce79… which no longer matches canonical registry content because active/lifecycle_state changed on close. DIGEST_MISMATCH.
- Root cause: R003-REV2 deactivate_allowance sets active/lifecycle_state/closed_at_utc but does NOT recompute allowance_digest (canonical_allowance digest includes active + lifecycle_state). The wrapper's own close corrupts the registry invariant the validator enforces.
- Severity: must (registry records must stay self-consistent).
- Classification: [HARD-REVISION] — single production file + test; frozen contract (allowance digest is part of the T0.3 canonical_allowance contract); no authority/custody/identity/migration/concurrency/compat/live-runtime/scope/policy change.
- Required fix: deactivate_allowance recomputes allowance_digest over the mutated record (active:false, lifecycle_state:closed) before writing; add a focused test asserting the closed record's digest equals canonical_allowance of the closed record; byte-lossless preservation of all OTHER bytes still required (the digest field value changes by design).
- Route: Luna [HARD-REVISION] (R003-REV3) → independent re-review → re-run close on R002-resume (or patch the record digest via the fixed close path idempotently) → commit → validator exit 0.


## OPERATOR DIRECTIVE (2026-08-20, after G0 PASS) — plan amendments before Batch 1 (supersedes conflicting inputs)

Source: user feedback attachment; full detail /tmp/grok-plan-improve-output.txt (P1-P10) + /tmp/grok-philosophy-sensecheck-output.txt (P1'-P10').

Incident: plan m7-dogfood-and-hardening-20260820-0835 blocked 2h on BrokenPipeError (unguarded stdout-tee print in resident/subagent.py). Five babysitter incarnations, 70 min, zero progress: read-only codex sandbox dies on bwrap in our container (116 dead); receipt status downgraded to failed while process returned rc 0 (watchdog re-armed same occurrence); two incarnations stood down on phantom PIDs.

Required amendments (authoritative):
1. NEW CARD T2.4 [XHARD] "Fixer transport honesty" — insert after T2.2, before T2.3; include in G2 and T7.2 shard 3. One enforcement point for the babysitter loop: goal text + exec argv agree on sandbox (bwrap probe -> danger-full-access + no-mutation + pre/post fingerprints, never --sandbox read-only on this host); receipt status + process rc are one fact (honesty downgrade -> exit nonzero); owner liveness = kill(pid,0) of recorded babysitter_pid; launched/running receipt with dead PID = failed, not active owner. No new claim API/rebind writer/seed ceremony/SHA pin.
   CRITICAL: fixes 7fe994abf (babysitter sandbox + false-success rc) and 0425372ec (stdout-tee BrokenPipe helper) live on epic branch (candidate astrid-first, gitdir /workspace/arnold-ref/.git/worktrees/astrid-first), NOT in G0 M1-M5 selection. Will be lost at promotion unless T2.4 (or T7.1) locks them in.
2. AMEND T2.2: watchdog re-arm of same occurrence requires a failed session receipt. Do NOT restate rc<->status in T2.2 — that invariant lives only in T2.4 (single enforcement point).
3. AMEND T4.1: MutationCapability for engine_runtime / recover-blocked binds import_root (live tree at epic.runtime_root + generation interpreter). Ambient megaplan_engine_root() from container PYTHONPATH is NOT authority input (resolves to read-only -live tree; causes phase_repair_commit_mismatch). SHA of that tree is telemetry. Execution protocol: every operator mutation against a live epic (recover-blocked, runtime-rebind, chain start) runs under the seed/import env.
4. AMEND T3.2 + T4.2: document + test FIXER-EXECUTABLE recovery contract for deterministic_phase_failure / repair_phase_contract: land patch on import_root -> (until T4.3 deletes seed gates) expected_head telemetry update without advance_generation -> runtime-rebind with milestone identity LABEL (m7), never sequence index (6) -> recover-blocked with --repair-commit + --failure-fingerprint + --repair-scope engine_runtime + --user-approved -> chain start --one, all under seed/import env. T3.2 stays observation-only (may emit typed request, never perform it). Operator executes only as last rung (babysitting 1.3); primarily a fixer contract.
5. PROTOCOL NOTE + T4.3: until seed-store/dispatch-current/MEGAPLAN_RUNTIME_LAUNCH_SEED/receipt-byte-equality gates deleted, every engine commit still requires expected_head bump + content-digest rebind — known tax, not recovery design. T4.3 acceptance: after cutover, same-import_root commit requires NO rebind or generation bump; a test still requiring the dance is a must-fail.
6. AMEND T3.3 / T7.2 / handoff template: verification isolation on cloud box uses danger-full-access + no-mutation + fingerprints, NOT --sandbox read-only (bwrap can't create userns here). Product read-only remains write-prohibition on production APIs proven by mutation spies. Shard failing because bwrap can't create a namespace = infrastructure, not product failure.
7. KEEP phase-contract fence: identical deterministic_phase_failure fingerprints cannot be mechanically retried without a new repair-commit bound to engine_runtime. T3.2 non-goals: automatic recover-blocked, automatic rebind, watchdog replay without a patch.
8. G3.5 / G6.4: name the PID dual — dead PID treated as live owner = over-enforcement (phantom stand-down = paralysis); live PID as authority = under-enforcement (already forbidden). T2.1 remains sole claim seam. G6.4 must find: fixer exits 0 / stands down / reports completed while target still blocked, even if a receipt field was later rewritten to failed.
9. T7.1 completeness: successor MUST contain best-effort stdout writer for managed-provider tees swallowing (BrokenPipeError, OSError) on begin/chunk/recovery/end writes (source: epic resident/subagent.py helper, 0425372ec). Absence is a must finding even though G0 didn't select the hunk.
10. Add incident-class mapping table after Settled Decisions: stdout tee -> T7.1 (not T4.*); babysitter sandbox -> T2.4 + P6 (not T3.3 product read-only); receipt+rc0 -> T2.2 + T2.4; phantom PID -> T2.4 + G3.5/G6.4; ambient vs seed engine root -> T4.1 import_root (no SHA pin, no advance_generation); recover-blocked + rebind + start -> T3.2/T4.2 (unblocker observation-only); two-commit tax -> protocol note + T4.3; 3/3 fence -> T2.3 keep. SD-009 still forbids mutating live epics as consolidation.

Not-to-do: no T4.4-shaped identity vector, no second occurrence owner, no SHA/epoch pins, no babysitter ceremony restoration, no automatic recover-blocked from T3.2, no advance_generation as recovery.

Routing: plan doc amendment executed by routed subagents (Luna brief-prep -> Luna [HARD] implementer on a fresh task worktree, then integration) AFTER R002 history rewrite lands. Todo list updated with T2.4. A fresh Grok 4.6 review of the amended frozen contracts (J4) will be routed before Batch 1 production code starts. Both fix commits to be preserved under safety refs (T0.1 additive) and bound into T2.4/T7.1 allowances.

## F-002/J3 hygiene chain — CLOSED (push unblocked)

- R002 complete re-review (mrc-4bc7e122…): R002-001 CLOSED, R002-002 CLOSED, R002-003/004 OPEN (citation to missing log heading).
- Root cause of R002-003/004: the 10-item OPERATOR DIRECTIVE log section was lost when R002-REV2's detached worktree copy overwrote the integration worktree log (based on pre-directive b26f3f5778). Restored the full section (heading + 10 items + incident table + not-to-do) into the log; committed 0241c065 ("docs(mrc): restore operator 10-item plan-amendment directive section").
- R002-003/004 closure verification (mrc-fe6da83d…): **CLOSED, pass with no findings**. Final tip 0241c065; validator valid; reachable-blob scan 36,474 blobs / 0 key matches; safety+seed refs intact; J1/J2/G0 receipts unchanged; no T4.4 material.
- F-002 chain complete: J3 judgment → R002 redaction + history rewrite → R002-REV2 (receipt/map/operator-amendment disposition) → R003 wrapper lifecycle (deactivation path) → R003-REV2 (lossless) → R003-REV3 (digest recompute) → REG-repair (closed-record digest) → complete re-review + closure review. All J3 push-unblock conditions met.
- NEXT: batch-0 push (explicit HEAD:fixer/runtime-convergence-r, force-with-lease of rewritten history after clean-scan proof per J3) → then plan-amendment verification + J4 → Batch 1.
- Supplement (F-002/J3 hygiene chain): The earlier closure claim covered the one-field graph only and is superseded for the current graph by F-004/J4. The historical section and its one-field findings remain preserved.


## F-004 — GitHub push protection found ADDITIONAL secrets in same artifact (J3 condition triggered)

- INT-b0push3 (mrc-e82c7c04…): force-with-lease push `HEAD:fixer/runtime-convergence-r` rejected by GitHub push protection: `push declined due to repository rule violations`, commit 1dbcc2ae9f, path `docs/arnold/maintenance-runtime-consolidation-evidence/baseline/T0.0/raw-cloud-container.txt:6` (the Config.Env array). J3's own residual-risk note said exactly this: "If a later scan finds additional push-blocking tokens in the same inspect, stop and route a new material judgment; do not silently broaden."
- Inventory (env-field names/lengths only; values never printed): Config.Env has 32 entries; DEEPSEEK_API_KEY already redacted (placeholder len 21); DISCORD_BOT_TOKEN len 72 (Discord bot-token format); GROQ_API_KEY len 56 (Groq API key format); MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_API_KEY_ENV is an env-NAME reference ("GROQ") not a secret; all other entries are plain config/paths.
- Local reachable-graph scan (count-only, custom pattern) passes because it only looks for the original captured key; GitHub's push protection uses its own broader secret patterns (Discord/Groq/etc.) — the local scan is not a substitute for GitHub's secret-scanning rule set.
- Decision: fresh Grok 4.6 material judgment (J4) per J3 — may the redaction be broadened to DISCORD_BOT_TOKEN + GROQ_API_KEY (and any other GitHub-flagged field) under the same single-field-per-record discipline, or must the artifact be handled differently (exclude/rotate/etc.)? Push stays blocked pending J4.


## F-004/J4 — evidence recorder record

- Finding: F-004. GitHub push protection rejected INT-b0push3 for `DISCORD_BOT_TOKEN` and `GROQ_API_KEY` in `docs/arnold/maintenance-runtime-consolidation-evidence/baseline/T0.0/raw-cloud-container.txt:6`.
- Field inventory (names and lengths only): `DEEPSEEK_API_KEY` placeholder length 21; `DISCORD_BOT_TOKEN` length 72; `GROQ_API_KEY` length 56.
- J4 ruling: `AMEND` / `A-extended`. Apply per-field redaction to the exact set `{DEEPSEEK_API_KEY, DISCORD_BOT_TOKEN, GROQ_API_KEY}`; retain the existing placeholder for `DEEPSEEK_API_KEY`; replace only the two newly authorized field values with their named placeholders; preserve all other fields and structure. Do not redact `MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_API_KEY_ENV` (field length 12) or any other non-flagged field.
- Push disposition: `BLOCKED`. J4 alone does not rewrite history or unblock the push. Push remains blocked until the receipt, chained digests, complete reachable-history rewrite, broader non-echoing scan, validator pass, and independent `[HARD-REVIEW]` pass are complete.
- Next route: Luna evidence recorder → Luna `[HARD-REVISION]` implementer → independent Luna `[HARD-REVIEW]` → existing integration/push role using `HEAD:fixer/runtime-convergence-r` and no additional refspec.

## F-004/J4 hygiene chain — CLOSED (push unblocked, round 2)

- J4 Grok judgment (mrc-21e4d426…): AMEND/A-extended — redact DISCORD_BOT_TOKEN + GROQ_API_KEY values only (exact set {DEEPSEEK_API_KEY, DISCORD_BOT_TOKEN, GROQ_API_KEY}); receipt adjudications/J4-grok-judgment.json (0f2bb741…); operator to rotate those keys outside consolidation.
- R004 [HARD-REVISION] (mrc-cdaef3df…): two-field redaction + F-004-redaction-receipt.json (2a5af4f6…, 1MB old→new map) + digest chain + history rewrite + broader scan (Discord/Groq/original patterns, 0 matches) + validator valid. Commit 45abf338fc "evidence(mrc): redact F-004 credentials and rewrite history". Worktree clean.
- Independent F-004 HARD-REVIEW (mrc-0ebfccde…): **PASS, no findings** — scope discipline, digest chain, broader scan, validator, R002 interaction (one-field reviews remain valid for one-field scope), J1/J2/J3/G0 untouched.
- All J4 push-unblock conditions met. NEXT: final push (explicit HEAD:fixer/runtime-convergence-r, force-with-lease vs a610c220da) → then Batch 1.


## BATCH-0 PUSH — SUCCESS (durable)

- INT-b0push4 (mrc-da46d423…): commit log closure record (e28cfe7f), broader clean scan (0 matches), explicit force-with-lease `HEAD:fixer/runtime-convergence-r` vs observed a610c220da → exit 0. Remote origin/fixer/runtime-convergence-r = e28cfe7fcee2c64fe67d7e1d5a53c0e5351119ef = local HEAD. Worktree clean. Safety refs untouched (local only).
- Batch 0 complete and durable: G0 PASS, plan amendment, F-002/F-004 hygiene, wrapper lifecycle, registry, log, all receipts.
- NEXT: preserve epic fix commits 7fe994abf + 0425372ec under safety refs (T0.1 additive) → route Grok J5 review of amended frozen contracts → Batch 1 (T1.1/T1.2/T1.3) under relaxed review cadence.


## T0.1 additive — epic fix-commit preservation — PASS

- Luna implementer (mrc-ba150c89…): read-only pack transfer from cloud candidate astrid-first (gitdir /workspace/arnold-ref/.git/worktrees/astrid-first); CAS-minted refs/heads/safety/maintenance-fixer-transport-7fe994abf → 7fe994abfb6fca372bfd2bf0d88945b3e6ab69d8 and refs/heads/safety/maintenance-stdout-tee-0425372ec → 0425372eca588a878dfffc5fbce44cbb2624d2c1; additive evidence milestones/T0.1/fixer-commits-custody.json ("provenance evidence, not launch authority — T2.4/T7.1 source, selected post-G0 by operator directive"; notes T0.2 follow-on binding needed); commit 0b879578. Nine safety refs total; six milestone tips + seed untouched; no push; cloud read-only.
- NEXT: Grok J5 review of amended frozen contracts (renamed from earlier "J4" label to avoid collision with the F-004 secret judgment) → Batch 1.

 
## J5 — amended frozen contracts — PASS (batch-1-go)

- Fresh Grok 4.6 judgment, role `JUDGMENT`, label `[XHARD-REVIEW]`: verdict **PASS**; `batch_1_may_start: true`; `must_findings: []`. Receipt: `docs/arnold/maintenance-runtime-consolidation-evidence/adjudications/J5-amended-contracts-grok-judgment.json`; invocation `mrc-4eca82d5636b24387d827808b7b390d458d01775cf7d38d0`; exit 0; elapsed 796.0748684999999s.
- Should findings are documentation/contract-lag only, not Batch 1 blocks: J5-SF-001 review-cadence wording still names per-card/G3.5 obligations; J5-SF-002 stale G0-blocked header and T0.3 pre/post schema wording; J5-SF-003 T2.4 must bind the actual `skills/babysitter/scripts/render_babysitter_goal.py` path and cover every sandbox-emitting routing mode; J5-SF-004 T3.2 tests remain typed request/checkpoint assertions, with executable recovery fixtures owned by T4.2.
- Batch 1 go: T1.1/T1.2/T1.3 may begin in parallel only after complete production-and-test allowances are frozen and proven disjoint; shared export/fixture/helper/test files serialize affected cards; G1 HARD-REVIEW is mandatory after the batch.
- Hard stop: no T2.4 or T7.1 implementation, allowance, or source-coverage claim until the additive T0.2 binding records `7fe994abf → T2.4` and `0425372ec → T2.4/T7.1`; do not rewrite G0, and Batch 1 must not absorb or modify either preserved commit.
- Review cadence: one review per subsection at G1/G2/G3/G4/G5/G6.3, with one-per-subsection complete-diff/call-graph/evidence reading; three end-stage Sol reviews are mandatory (architecture/authority/simplification covering G3.5+G6.4; evidence/selection completeness and validator integrity covering T7.1/T7.5; G7 promotion recommendation after canonical validator pass). Authority-changing dispositions remain fresh Grok/JUDGMENT; reviewers remain read-only and independent; must findings block.
- Joint reading preserves no standalone G3.5 invocation claim, serial T4.1 → T4.2 → T4.3 followed by one G4, existing G7.4-pre/post canary surfaces, T2.4 Grok `[XHARD]` implementation with Luna G2 review, M5 report-only behavior, and Live Tree Authority as sole authority.
- Next: T1.1/T1.2/T1.3 brief-preps.

## G1 HARD-REVIEW — findings (7 must) → T1.3 revision chain

- Reviewer: independent Luna (mrc-2ce733dd…). Focused shard 334 passed (99+235). T1.1 rendering purity PASS; T1.2 policy/reporting purity PASS (ledger/projection are evidence seams); legacy parity PASS; determinism PASS; allowance boundaries PASS.
- Must findings (all in T1.3 efficiency surfaces):
  - G1-F-001 [XHARD-REVISION]: efficiency_sources.py adapters accept+retain mutation-capable provider objects (store: Any, only named reads called but no mutation-method rejection). Violates T1.3 "no mutation-capable provider accepted".
  - G1-F-002 [XHARD-REVISION]: efficiency_routing.py accepts opaque Callable seams (prior_key_lookup, initiative_eligible) without read-only protocol/capability check — hidden authority reachability.
  - G1-F-003 [HARD-REVISION]: join_observation_envelope promotes missing owner environment into coherent envelope (expected_env from first present; missing treated compatible) — incomplete evidence supports proposals.
  - G1-F-004 [HARD-REVISION]: efficiency_analysis _exact_accepted_outcome_economics divides known-duration sum by full denominator (missing duration → misleading numeric claim).
  - G1-F-005 [HARD-REVISION]: efficiency_clustering same partial-economics defect (avoidable_impact numeric from incomplete time).
  - G1-F-006 [HARD-REVISION]: NormalizedCall/ClusterEvidence accept censored=True with exact elapsed/time + no lower bound — right-censored treated as completed.
  - G1-F-007 [HARD-REVISION]: RootCauseCandidate/DailyEfficiencyProposal permit empty occurrence/evidence refs; routed proposals emitted without underlying evidence links.
- Routing: F-001+F-002 → fresh Grok 4.6 [XHARD-REVISION] (G1-RX); F-003..F-007 → fresh Luna [HARD-REVISION] (G1-RH). Both touch efficiency_sources.py (F-001, F-003) → SERIAL: Grok first, then Luna. After both: fresh independent G1 re-review of complete Batch-1 diff.


## G1 complete re-review — F-003..007 CLOSED; F-001/F-002 OPEN → G1-RX2

- Reviewer: independent Luna (mrc-dde41450…). Focused shard 347 passed.
- G1-F-003..007 CLOSED (envelope env check, denominator preservation, censored lower-bound enforcement, ref-required candidates/proposals — all verified by direct assertions).
- G1-F-001 OPEN (must, XHARD-REVISION): _seal_named_reads/_seal_callable wrappers retain the original provider via closure + bound-method __self__ (bound_method_self_is_original True); _is_writer_named vocabulary misses equivalent writer names (commit() admitted).
- G1-F-002 OPEN (must, XHARD-REVISION): PriorKeyLookup/_seal_routing_operation retain the raw callback via closure; _ROUTING_MUTATION_VERBS omits commit-style names.
- Root cause: name-denylist + closure-retention sealing is bypassable; the requirement is NO original provider/callback reachability and NO mutation-capable surface — a whitelist of exactly the declared read surface, with the original object unreachable through any wrapper.
- Route: fresh Grok 4.6 [XHARD-REVISION] (G1-RX2) → fresh independent Grok re-review (original gate's required model) → then G1 closeout.


## G1 — Batch-1 purity and conservative-evidence review — PASS (after 2 revision rounds)

- G1 review (mrc-2ce733dd…): 7 must findings. Focused shard 334 passed (99+235).
- G1-RX (Grok, f982fb2f0d): sealed providers/routing; F-001/F-002 partially fixed but re-review found closure/bound-method __self__ retention + deny-list bypass (commit() admitted).
- G1-RH (Luna, 2e5ebcd3ef): F-003..007 closed (missing-env → INCOMPLETE/unknown; partial durations → None; censored requires lower bound; candidates/proposals require refs). Focused shard 248 passed.
- G1 complete re-review (mrc-dde41450…): F-003..007 CLOSED; F-001/F-002 OPEN (347 passed).
- G1-RX2 (Grok, 1a10d5215f): exact-whitelist + private 1-tuple keepalive + weakref proxy; original provider unreachable; commit()-style writers rejected pre-read; raw callbacks refused.
- G1-RX2 Grok re-review (mrc-46b6ef48…): **PASS, no findings**. Data-model callables (copy/count/etc.) filtered, not escaped; _keep is the chosen lifetime mechanism; fail-closed for non-weakref-able providers; G1-F-003..007 not reopened.
- G1 disposition: PASS. Batch 1 complete (T1.1+T1.2+T1.3 + revisions) at HEAD 1a10d5215f. Focused shard 347+ passing.
- NEXT: commit accumulated log → Batch 2 (T2.1, T2.4 [XHARD], T2.3, T2.2 per amended plan) with additive T0.2 binding for 7fe994abf/0425372ec BEFORE T2.4 (J5 hard stop).


## OPERATOR DIRECTIVE (2026-08-21) — review-process simplification (supersedes prior cadence)

- User directive: (1) orchestrator authors the cards directly — NO Luna brief-preparation subagent for remaining work; (2) ONE Grok revision/review per task — the single Grok reviewer is told it is the ONLY review, so it must be comprehensive; (3) at the very end of the whole run, THREE whole-system reviews with GPT-5.6 Sol (`codex:gpt-5.6-sol`).
- Implementation: orchestrator drafts each card brief itself (wrapper still enforces hashing/allowances/routing); one Grok XHARD-REVIEW per task (role XHARD-REVIEW → grok-4.6) with an explicit "single review" instruction; at most one revision round per finding (if a must finding survives one verified repair, fresh Grok adjudication decides accept-residual vs block — no unbounded chains); the three end-stage reviews are Sol-based (architecture/authority/simplification; evidence+validator completeness; final promotion).
- Wrapper impact: add a `gpt-5.6-sol` model route (hermes launcher --model=codex:gpt-5.6-sol) + role mapping so SOL-REVIEW dispatches route correctly; one bounded revision.
- Luna still used for mechanical roles per model routing (integration, validation, evidence recording, report assembly) unless the directive says otherwise — it explicitly removed only brief-preparation from Luna.


## Baseline test note (pre-existing, not a Batch-2 regression)

- `tests/cloud/test_watchdog_wrappers.py::test_long_running_superfixer_wrappers_pin_syntax_checked_source_snapshot[arnold-watchdog-ARNOLD_WATCHDOG]` fails at fce base, at 595c3513d7 (pre-T2.4), at 11d4126b6e (pre-T2.3), and at HEAD. Assertion expects `trap 'rm -f -- "$ARNOLD_WATCHDOG_SNAPSHOT_PATH"' EXIT`; the wrapper uses a `watchdog_snapshot` re-exec + cleanup-path-from-BASH_SOURCE mechanism instead. Stale test vs current wrapper; pre-existing.
- All Batch-2 focused tests that pass: T2.1 schedules (27), T2.2 dispatch + controller (8+17), T2.3 cutover (8) + classifier (28), T2.4 babysitter (39), plus wrapper tests excluding the stale snapshot assertion.
- Recorded for G2 reviewer: this assertion is out of Batch-2 change scope; treat as pre-existing baseline incompatibility, not a must finding on Batch 2 (do not block G2 on it).


## G2 — Batch-2 authority-entry review — PASS

- Single Grok review (mrc-578fe9cd…): PASS. One claim point (T2.1 ScheduleService.claim/claim_superfixer_occurrence CAS), one receipt identity (typed report/effect separation, exactly-once), one repair-eligibility path (quality labels L1 only via _is_evidence_bound_deterministic_quality_block; watchdog DISPATCH_DECISION from classify_repair_dispatch), T2.4 transport honesty verified; no observation→authority conversion; M5 report-only.
- Should residuals (non-blocking): G2-S001..S005. Notable: S003 reconcile_terminal_runs unfenced (pre-existing); S004 M5 controller authorized=True (pre-existing, wrapper default report-only); S005 supervise queues repair without classifier for review_rework_exhausted/binding-drift (second queue seam — flagged for end-stage Sol review 1 aggregation/simplification scope).
- Baseline note honored: stale watchdog snapshot test excluded (fails at fce; pre-existing).
- Batch 2 CLOSED. NEXT: Batch 3 (T3.1 migration running; T3.2 unblocker; T3.3 six-hour auditor) → G3.

