# Independent Sol pre-execution freeze oracle — v8

## Verdict

**PASS_FREEZE**

- Model: `gpt-5.6-sol`
- Reasoning effort: `xhigh`
- Reviewed at: `2026-08-29T21:37:45Z`
- Decision scope: contract/task freeze only; this decision does not itself authorize a push or any merge to `main`.

## Exact reviewed identities

- Plan v8: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Tasklist v8: `88adb2e2e849285c7f83c924ef32c4fab12f1d05d3d4820dab0813f40c445e43`
- Luna v8 finding: `7a09c3c827ca302f12d26a4bfb51bc95f73c6d99da03951e79150b7dd020540a`
- Luna v8 receipt: `2691b341c030e51056987f1aeb02fa130af75f22a901d5847cdf1c94b2d0f2f6`
- Sol v8 contract-fix receipt: `7f43fa03172571de86c3f031e9e5a6d64fb15a9698f21aaf76420213ddbe7813`
- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Agent goal: `cc9d45214a38312fb652ca216d1fbc1964b1d5d7e7b94f26b05b7b6a26c1b032`
- Custody: `29f7ad58cfa9057ccc02006d70fede01ab5f4a38a3e351acd762a545ed3ae608`
- Sol v7 BLOCKED review: `f29f375e3341425d4970377096f91505972fb1a4b8805ccb3674cbfb3be3ef9d`
- Archived plan v7: `3e76fc3c9eeb8fbd6580d1217db341c1c3e9f16a4be3552eadddbef2ccd9276f`
- Archived tasklist v7: `70165356577b13f9d4a7841aaa33322839cd7f150db0bf0da2aa3c456e8bf039`
- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Reviewed planning HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`

The complete North Star, agent goal, custody baseline, final plan v8, final tasklist v8, Sol v7 BLOCKED review, Luna v8 review/finding, contract-fix receipt, archived v6/v7 load-bearing findings, and relevant source surfaces were read. The plan/tasklist hashes still match the Luna-bound identities and were not changed after Luna review.

## The four v7 blockers are corrected

1. **Fresh Luna before separate Sol freeze:** plan §2.3 and tasklist lines 3 and 1076–1078 require the ordered Luna-then-Sol sequence on the same final digests. The fresh Luna receipt is bound to the exact plan/tasklist hashes above and returns `PASS_LUNA_V8`; this decision is the separate later Sol judgment.
2. **Inventory digest custody:** plan §2.4 and tasklist NBF-05 permit only a provisional, explicitly non-authoritative Batch 3 artifact digest. NBF-07 alone records the authoritative external inventory SHA-256 after all candidate changes are committed and the exact candidate SHA is frozen. `source_inputs_sha256` remains deterministic and non-circular.
3. **NBF-06 disposition regression:** `tests/arnold_pipelines/megaplan/test_worker_disposition.py` is explicitly NBF-06-owned and appears in NBF-06 focused validation and the authoritative final suite.
4. **Custody-safe clean proof:** plan §4.24 and NBF-07 require clean tracked worktree/index state plus exactly `.oracle/briefs/planner-sol.md` as the sole permitted untracked path, hash-pinned to `6d070eae4e5a09f7575ffffaef91fc95c3cd1a32095baa3219f050d37e7fe8a0`. That digest matches the present artifact. All other untracked paths must be committed, moved outside candidate content, or rejected before candidate freeze.

## Preserved load-bearing contracts

- **Worker disposition:** `DispatchOutcome(kind=worker_disposition)` is lossless, accepted-launch-only, and retains disposition, receipt, fingerprint, phase/spec, worker, and timing identity. It maps only to one `worker_terminal_outcome(outcome_kind=worker_disposition)`, validates the existing record-before-signal disposition, never re-appends it, never coerces to ordinary/provider failure, closes once, and breaks provider-exhaustion consecutiveness without entering degradation. Ownership is coherent across NBF-01 schema/replay, NBF-02 intake/writer integration, NBF-03 traces, NBF-04/05 real death producers, and NBF-06 interleavings.
- **Inventory and exact SHA:** the generated inventory excludes git identity, itself, and self-digest from `source_inputs_sha256`; NBF-05 owns deterministic discovery and provisional review evidence, while NBF-07 commits first, freezes one clean candidate SHA, validates without mutation, keeps evidence external, restarts the cycle after any mutation, and records the final external artifact digest only against that SHA.
- **T8 streak:** only accepted canonical `provider_exhausted` worker outcomes create/increment the keyed streak. Probe results and creation/consumption of single-use `provider_recovery_verified` preserve it; the authorized matching child may be observation two; success resets; different-key exhaustion rekeys at one; ordinary failure and worker disposition break consecutiveness; only an authoritative provider-failure-key change otherwise resets/rekeys.
- **Task ownership/dependencies:** all seven tasks remain distinct. NBF-06 has a hard dependency barrier through NBF-05; NBF-07 alone owns authoritative post-rebase validation. No second scheduler, admission authority, journal, projection, terminal writer, rotator, service, store, or family lease is introduced.
- **Model policy:** every implementation/review task is Normal/GPT-5.6 Luna. GPT-5.6 Sol remains reserved for planning and Oracle gates; the temporary Sol authorization is correctly treated as permission, not a mandatory executor switch. No task is `[XHARD]`.
- **Delivery/no merge:** final review and pre-push acceptance bind one exact candidate SHA; push uses an explicit candidate-branch refspec, rewritten history requires observed-tip `--force-with-lease`, and remote-tip identity is mechanically verified. No merge to `main` is authorized without explicit user approval.

## Source corroboration

The plan is anchored to the actual pre-implementation gaps at the reviewed source base: the current runtime gate at `cloud/runtime_attestation.py:2961` covers seed/interpreter binding but not the frozen joint admission contract; `workers/_impl.py:7347` still has the production no-WBC legacy branch and raw refresh/require/source preflight; `workers/omp.py:1173` statically admits `openrouter/stealth/ox-alpha` without the required joint live-membership gate; `model_seam.py:502` classifies that expired ID; `chain/source_admission.py:259` retains a separate preflight; babysitter launch reaches `run_managed_command`; `IncidentLedger.append_event` remains the canonical existing journal door; and the named launcher, resident, watchdog, ensure-watchdog, fan, agent-loop, operator, and additional discovered signal paths still require repository-wide closure. The task ownership and generated/static verification work directly cover those gaps rather than assuming they are already fixed.

No material contradiction, omitted load-bearing contract, stale-review binding, ownership overlap, model violation, delivery ambiguity, or unauthorized merge path remains. The exact plan v8/tasklist v8 pair above may be frozen.
