# Task: Extend Sequential Model Fallbacks into the managed-agent profile epic

Status: originally shaped as seven milestones on 2026-07-11, then consolidated into the two-sprint execution contract described by `README.md`, `NORTHSTAR.md`, and `chain.yaml`. Sizing was revalidated on 2026-07-13: the authoritative shape is two sprints of roughly two human-weeks each, connected by a machine-readable Sprint 1 contract handoff. This file retains the original request; the authoritative execution inputs are the two sprint briefs and locked decision record.

The user wants a Megaplan epic for one unified managed-agent system covering both resident-launched agents and subagents launched by those agents.

Reuse the existing `sequential-model-fallbacks` initiative. Do not create a parallel initiative unless repo evidence proves this one cannot coherently own the work. Preserve existing work and inspect current initiative/code state before editing.

Shape durable `megaplan-initiatives-v1` assets only under `.megaplan/initiatives/sequential-model-fallbacks/`. Update its North Star, README, `chain.yaml`, milestone briefs, and any research/decision/handoff material needed so the chain covers:

- one shared D1-D10 difficulty/profile resolver for Megaplan and resident-managed agents;
- D5 semantics and deterministic profile/model/reasoning/tool/budget resolution;
- ordered model fallback based on existing partnered-5 machinery, with canonical retry classes and fail-closed behavior after possible mutation;
- immutable complete root-brief/task references and hashes propagated to all descendants;
- a first-class managed child-launch path, not arbitrary unmanaged shell spawning;
- ancestry, immutable Discord/request provenance, root-only user delivery, durable structured child results;
- inherited model/tool/sandbox/cost ceilings, root-scoped attempt budgets, visited-spec loop prevention;
- bounded nesting/fanout (evaluate proposed defaults depth 2, four children per parent, eight descendants per root);
- manifest/schema migration with v1 dual-read compatibility;
- observability, deterministic resolution receipts, cost/time/token limits, restart/resume evidence;
- acceptance tests proving scalar compatibility, D1-D10 routing, D5 behavior, identical fallback classification across dispatchers, no post-mutation fallback, complete brief hashes, immutable custody, root-only delivery, depth/fanout/budget enforcement, no privilege expansion, and legacy compatibility.

Decompose into sprint-sized milestones with explicit dependency/handoff artifacts. This is cross-cutting public-contract and custody work: score overall plan difficulty 5/5 and use `partnered-5`, vendor `codex`; default `full` robustness and use high depth only where the architectural risk warrants it. Do not use xhigh/max. Keep merge/driver policy suitable for later unattended execution, but do not start the chain in this task.

Reconcile overlap with `discord-resident-delegation-delivery-corrective`: that initiative owns Discord lifecycle/delivery; this initiative owns generic profile/fallback/brief/nested-agent contracts. Encode explicit dependency or coordination boundaries without absorbing unrelated Discord work.

Validate YAML/schema, initiative layout, referenced paths, dependency ordering, and focused editorial tests. Report the final epic name, milestone count and one-line milestone sequence, validation evidence, and any human decisions still required. Do not launch or resume any cloud chain.
