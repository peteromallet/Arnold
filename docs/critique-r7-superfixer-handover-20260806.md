# Critique R7 superfixer — handover

**Updated:** 2026-08-06 (UTC)  
**Status:** recovery work partially completed; the critique chain has **not** advanced.

## Mission and execution surface

The immediate mission is to **fix the fixer itself, deploy the corrected runtime
to the cloud machine, and durably move the existing four-phase critique epic**;
starting a replacement epic would lose the preserved occurrence and is not the
goal.

- Cloud host: `root@159.69.51.216`
- Resident container: `megaplan-cloud-agent-resident-only`
- Cloud workspace root: `/workspace`
- Approved editable runtime: `/workspace/runtime-candidates/arnold-r7-fresh-child-20260805`
- Current cloud runtime branch: `recovery/critique-r7-splitter-f3b952be`
- Current runtime commits: `4947c2ca1` (reference-closure repair), then
  `dfc98e9c8` (launcher/runtime binding and completion-driven loop)
- Existing epic/session to resume: `critique-ledger-accountability-v3-r7-launch-20260805`

**Current status at handover:** v6 is terminal `failed` (provider return code 2);
the v6 parent has no live process or WBC effect. The epic remains at milestone 0
`cl2-ledger-replay`, `current_state=blocked`, with no completed milestones. The
source repair, launcher fix, ticket update, and resume-cursor rearm are durable.

**Latest live update:** the corrected runtime was CAS-rebound successfully at
`2026-08-06T16:00:55Z` (identity
`2d1f0623cd6b58021ba2d85303ce471de9afbc4032ffbfa3f3021514b3512835`). The same
managed Hermes session was then continued as
`subagent-20260806-160201-77559b7a` with `ARNOLD_PATH` pinned to R7 and
`ARNOLD_RESIDENT_UNBOUNDED_REQUEST=1`. That continuation is live; canonical
recovery/finalize proof and milestone advancement are still pending.

An isolated Luna worktree also contains `3bea921a…`, but it is based on a
divergent line and changes/deletes overlapping runtime files. It has **not** been
cherry-picked into R7 and must not be merged wholesale during this recovery.
Use the content-addressed R7 line above unless a new Sol-reviewed migration
explicitly reconciles that patch.

## Target

- Session: `critique-ledger-accountability-v3-r7-launch-20260805`
- Workspace: `/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold`
- Chain spec: `.megaplan/initiatives/critique-ledger-accountability-v3-r7-20260805/chain.yaml`
- Plan: `cl2-wbc-backed-ledger-20260805-2140`
- Milestone: `cl2-ledger-replay` (index 0)
- Current canonical state: `blocked`, completed milestones `[]`
- v6 fixer run: `subagent-20260806-145651-4c581f6a`
- Evidence: `.megaplan/incident-evidence/critique-r7-superfixer-20260806-145651-4c581f6a/`

The run was manually relaunched as a fresh v6 occurrence after the obsolete v5/77b
worker was cancelled. No second chain or duplicate critique session was created.

## What actually happened

The deterministic blocker was a task-reference closure bug, not a model-quality
judgement:

1. `split_high_complexity_tasks` replaced `Tn` with `Tn_impl` and `Tn_proof`.
2. Downstream `depends_on` and `dependency_reasons` still referenced the removed
   `Tn` IDs.
3. Finalize feasibility rejected the candidate with 12 `dependency_unknown`
   findings and `dependency_graph_invalid` (fingerprint
   `382e25a279dbb2b7784f56d8a0b59eae9422a0625d48c9bb1185aa3fec4a33df`).
4. The planner-repair circuit opened. The old projection also lost the
   `latest_failure`/`resume_cursor` needed by the supported recovery command.
5. The old worker treated a clean handler return as success even though no
   admitted finalize artifact existed, which produced the misleading “finalized”
   state and repeated notifications.

Evidence reproduced the blocker byte-for-byte. Sol stage 1, the eight read-only
Flash investigations, and Sol stage 2 all agreed that the same occurrence should
be repaired and resumed, with complete reference closure and a fresh authority
transition.

## What v6 did accomplish

Sol’s validated handoff:

- Handoff schema: `arnold.superfixer.recovery_handoff.v1`
- Earlier handoff ID: `sha256:00adf9…` (the final rendered handoff is in the evidence directory)
- Route: same-occurrence `repair_control_plane_then_migrate`
- Horizon B: update the existing ticket; do not create a second ticket

The DeepSeek Flash fixer then:

- created recovery branch `recovery/critique-r7-splitter-f3b952be`;
- committed the source repair as `4947c2ca1` (`fix(finalize): rewire downstream task references after split (reference closure)`);
- rewired dependencies, reasons, coverage, sense checks, plan-step references,
  and user-action references with fail-closed collision handling;
- added the closure assertion, circuit rearm helper, and focused splitter test;
- updated the one canonical follow-up ticket
  `ticket-r7-superfixer-v4-20260806-1329`;
- installed the editable runtime and recorded a valid content identity for the
  repaired runtime;
- durably rearmed `latest_failure` and `resume_cursor` in the plan through the
  engine helper.

No chain state, WBC effect, notification effect, or canonical milestone was
advanced by v6.

## Why v6 still failed

There were two independent execution defects.

### 1. The “unbounded” flag did not reach the actual agent

The managed worker exported `ARNOLD_RESIDENT_UNBOUNDED_REQUEST=1`, and the pinned
R7 `AIAgent` supports completion-driven mode (`max_iterations=None`). However,
`launch_hermes_agent.py` put the project checkout first on `sys.path` and could
therefore import the target checkout’s older `arnold.agent.run_agent`, whose
default remained 90 iterations. DeepSeek Flash consequently stopped at:

> `Reached maximum iterations (90). Requesting summary...`

It stopped after editing/committing and before tests, runtime rebind, or canonical
re-entry. This is a launcher/runtime identity defect, not a DeepSeek reasoning
failure.

### 2. The runtime-rebind verifier rejected the control interpreter

The first provenance receipt used the same Python executable as the control
runtime, so CAS rebind correctly refused it with:

`chain_runtime_binding_drift: offline runtime interpreter is not independent from the control runtime`

The container does contain the supported independent interpreter at:

`/tmp/arnold-independent-python3.11`

The next receipt must be generated with that executable for the final repaired
revision. Do not weaken or bypass the verifier.

## Fixes already deployed on the approved runtime

The editable R7 runtime is:

`/workspace/runtime-candidates/arnold-r7-fresh-child-20260805`

Its recovery branch currently contains:

- `4947c2ca1` — task-reference closure/finalize/circuit repair
- `dfc98e9c8` — launcher binds imports to `ARNOLD_PATH` and passes
  `max_iterations=None` for resident completion-driven runs

The launcher patch is the root fix for the 90-iteration regression. It preserves
the project as the tools’ cwd but forces the occurrence-bound runtime to the
front of `sys.path`, skips legacy distribution preference for resident runs, and
constructs the R7 agent in explicit completion-driven mode.

## Exact next steps

1. Verify the approved runtime is clean at `dfc98e9c8` and the launcher import
   test resolves `arnold.agent.run_agent` from the R7 runtime, with
   `AIAgent.max_iterations is None`.
2. Generate a new provenance receipt for revision `dfc98e9c8` using
   `/tmp/arnold-independent-python3.11` and the supported
   `arnold_pipelines.megaplan.cloud.runtime_provenance` command. Store the
   receipt and identity under the v6 evidence directory; do not edit state files.
3. Execute the supported `chain runtime-rebind` CAS command for the same
   session/plan, with:
   - from runtime identity: the currently bound runtime;
   - to runtime identity: the new receipt’s content SHA;
   - expected milestone: `cl2-ledger-replay`;
   - expected plan: `cl2-wbc-backed-ledger-20260805-2140`;
   - direction: `cutover`;
   - actor: `arnold-recovery`;
   - both runtime identity and independent provenance receipt paths.
4. Continue the failed managed Hermes session using the supported
   `follow_up_managed_subagent` seam (same run lineage and session ID), with an
   occurrence-bound message to:
   - use the new independent receipt;
   - re-run focused tests or the exact-candidate validator;
   - execute Run Authority → Custody claim/epoch → WBC recovery effect;
   - use `recover-blocked` through its canonical producer;
   - run ordinary finalize and verify accepted artifacts, cleared circuit,
     released custody, cursor advancement, and milestone advancement.
5. Observe authoritative state and effects. Do not stop at a commit, a PID, a
   successful rebind, or a model summary. The success condition is the chain
   milestone moving beyond index 0 with matching runtime/request/grant/claim/WBC
   identities and exactly one terminal notification.

### Trigger command after the rebind

Use the resident-managed continuation seam, preserving the failed run’s
`resident_0ab6917925864a8cbda6a043fc46dcfa` session and its launch provenance.
Do not launch a free-standing Hermes process and do not create a new chain:

```bash
R=/workspace/runtime-candidates/arnold-r7-fresh-child-20260805
P=/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold
RUN=subagent-20260806-145651-4c581f6a

PYTHONPATH="$R" python -P -m arnold_pipelines.megaplan.resident.subagent follow-up \
  --run-id "$RUN" \
  --project-dir "$P" \
  --idempotency-key "critique-r7-rebind-and-resume-dfc98e9c8" \
  --message-file /path/to/occurrence-bound-recovery-message.md
```

The resident caller must supply its validated inherited delegation provenance;
the resident Discord/profile seam is preferred. If invoking the library seam
directly, pass the exact `launch_provenance` loaded from the failed manifest as
`caller_provenance`—never invent a new marker. The message must name the new
receipt/identity paths and require the full Run Authority → Custody → WBC →
recover-blocked → ordinary-finalize proof.

If the continuation cannot be attached because the failed parent lacks valid
provenance, create one new occurrence-bound fixer schedule for the **same** chain
and session, reusing this evidence and handoff; do not use `--fresh`, create a
new chain, or hand-edit JSON/SQLite.

## Stop conditions

Stop effects and return to Sol only for a real identity/CAS/provenance conflict,
competing owner/effect, failing validator, dirty/non-descendant runtime, repeated
fingerprint, stale authority, partial publication, or an actually unavailable
provider/owner. A source repair, interpreter receipt, or runtime rebind is not an
external gate.

## Evidence index

- `evidence-pack.md` — redacted identity, state, and failure evidence
- `sol-stage1.md` — first Sol judgement and Flash question set
- `swarm/` — eight read-only Flash reports
- `recovery-handoff.json` / `sol-stage2.md` — executable Horizon A and durable Horizon B
- `provider.raw` / `run.log` — v6 execution record and the 90-iteration failure
- `runtime-provenance-splitter-recovery.json` — old control-interpreter receipt;
  replace with an independent-interpreter receipt for `dfc98e9c8`
- `fingerprint-before.json` — authoritative before fingerprint

**Do not report this epic as running or fixed until the canonical chain state and
after-proof show actual milestone advancement.**
