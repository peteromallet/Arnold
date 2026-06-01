# Deferred / superseded milestone drafts (v1)

These are the v1 milestone briefs. After the pre-mortem (briefs/validation/premortem/SYNTHESIS.md)
the epic was re-aimed around the guiding principle: **share what other tools use; don't generalize
planning-only machinery.** See briefs/pipeline-unification-EPIC.md (v2) for the active plan.

Status of each:
- `m2-profile-agnosticism.md` — SOURCE for the active **m2-dispatch-service** (expanded with
  dispatch-as-a-service + Arnold reconciliation).
- `m4-planning-packification.md` — SOURCE for the active **m3-planning-as-pack** (plus collapsing the
  third next-step encoding `workflow_next`).
- `m5-config-substrate.md` — its **RunConfig + services** half feeds active **m4-shared-substrate**;
  the full-HandlerContext "pure handlers" + 81-field typing is DEFERRED (planning-only generality).
- `m6-realizer.md` — its **mode-keyed evidence seam** feeds active **m4-shared-substrate**; the
  symmetric 5-method Realizer Protocol + `capabilities` tuple is DEFERRED.
- `m3-auto-inprocess.md` — DEFERRED entirely (the auto.py in-process port / single execution path is
  planning-only orchestration; keep two engines; revive only on a real second-tool need). Its
  `test_auto_drive.py` oracle is still worth landing early as standalone CI.
