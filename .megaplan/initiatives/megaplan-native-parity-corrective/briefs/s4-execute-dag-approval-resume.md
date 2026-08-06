# S4 - Tiebreaker, Finalize, Human Decisions, and Durable Reentry

## Objective

Author the remaining planning/finalization decision topology and prove that
every human suspension resumes at the exact semantic point under current Run
Authority and Custody—not from a marker, receipt, projection, or stale lease.

Make `NP-GT-003` in `../GOLDEN_TRACE_CONTRACT.md` green as the normative
same-run clarification suspend/cross-host resume trace.

## Product scope

- tiebreaker researcher and challenger in parallel, synthesis, and full typed
  human decision vocabulary: pick, reiterate, replan, escalate, abort, suspend;
- replan state reset and rejoin to the ordinary plan/finalize path;
- finalize as a typed phase, visible baseline-selection fallback to revise,
  retry, and scoped re-finalization;
- prep clarification, tiebreaker, finalize escalation, and applicable control
  gates as named durable suspension/reentry points.

## Required work

- Preserve deterministic semantic paths for all tiebreaker children and causal
  fan-in to synthesis/decision.
- Attach capabilities and accepted Run Authority decisions to human actions;
  maintain WBC suspend/resume lineage separately from subject attempt identity.
- On resume, reacquire or validate the exact Custody lease/epoch and current
  coordinator fence for the same semantic reentry target.
- Ensure suspension does not hold an indefinite lease. Expiry, transfer,
  reclaim, cancellation, and duplicate decisions use M11's lifecycle.
- Relocate WBC producers to lowered tiebreaker/finalize nodes and delete/fence
  component topology, handler dispatch, private state cursors, and marker-only
  resume paths.
- Run kill/restart/resume and stale-human-decision mutations from checkout,
  wheel/sdist, and the pinned custody-compatible runtime.
- Emit the `NP-GT-003` receipt with ordered suspend/checkpoint/reclaim/resume,
  Host A/Host B epochs, exact decisions, and executable digests.
- Exercise mixed-version human suspension: suspend multiple v1 runs, deploy v2,
  and require each run to resolve its exact retained v1 executable, dependency
  lock, prompt/tool assets, and schemas or consume an accepted typed migration/
  new-attempt/quarantine decision. Prove referenced v1 assets are ineligible for
  garbage collection while any resumable run depends on them.
- Treat prompt content/assets, model/tool configuration and schemas as part of
  the call/executable binding. A completed durable LLM/tool result is replayed,
  not recomputed after a three-day human wait or host change.
- Consume S3A's canonical execution-plane binding and shared resume selector;
  no editable status/registry may choose the resume plane or cursor.
- Treat standing migration compatibility as eligibility only. Every applied
  migration consumes one accepted RA decision binding exact from/to and state
  transform digests, then opens the required fresh attempts/current Custody.
- Accept one distinct human answer by CAS. Same-submission replay returns the
  original result; every different losing submission is durable privacy-safe
  `human_answer.rejected_late` evidence and never route authority.
- Through two independent production-adapter clients, force distinct valid
  answer-versus-answer and accepted-answer-versus-cancel contention at the
  canonical CAS boundary in both release orders. Exactly one compatible
  transition commits; losing answer/cancel facts remain durable and cannot
  resume or rewrite terminal truth. Bind the receipt to the certified
  linearizable store/service operation and its adapter/schema provenance.
- Remove the S3B tiebreaker/finalize seam. Generate a closed typed finalize-to-
  legacy-delivery serializer whose accepted upstream decision already names
  the entry; register durable writes, prove route inertness and expire it in S5.

## Semantic gate

- Source visibly expresses parallel researcher/challenger, synthesis, every
  decision route, replan rejoin/reset, finalize fallback, and scoped retry.
- Tiebreaker pick/reiterate/replan/escalate/abort and finalize failure/recovery
  scenarios execute from lowered topology.
- Deleting old tiebreaker/finalize route metadata cannot alter the trace.

## Custody-adoption gate

- Kill/restart resumes at the same semantic path with the correct four-domain
  identity joins and without repeating accepted effects.
- Stale approval, stale marker, stale coordinator fence, stale custody epoch,
  wrong target, and forged WBC success cannot resume or advance.
- Human decisions are accepted through Run Authority; WBC records the durable
  boundary history but is never treated as permission.
- Source program/topology digest, call-site-policy digest, or WBC contract
  version drift during suspension cannot silently resume. Resume uses the
  pinned version or an accepted typed migration/new-attempt/quarantine decision,
  with a new subject/WBC attempt and current custody epoch as applicable.
- `NP-GT-003` passes all stale fence/epoch/digest, forged projection, and wrong
  human-input mutations before plan enters.
- v1/v2 mixed suspended-run and premature-GC mutations prove exact pin
  resolution, explicit disposition, and no silent continuation on v2.
- Duplicate/late human answers and wrong-plane resume mutations retain evidence
  but cannot consume another decision or enter product code.
- Answer/cancel races produce one accepted transition under real
  production-adapter contention, not merely a serialized harness schedule.

## Do not close if

- Researcher/challenger execute sequentially while source or proof claims
  parallelism.
- `SUSPEND` is translated to terminal halt without durable reentry.
- Resume authority comes from status/projection state or a historical receipt.
- A suspended path recompiles under changed source, policy, or WBC contract
  without an explicit accepted drift decision.
- A pinned executable/prompt/schema is missing while its run remains resumable,
  or resume silently repeats a previously durable LLM/tool call.
- Human arbitration is application read/check/write, a local mutex, or an
  in-memory CAS presented as release proof.
