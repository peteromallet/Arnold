# T0.0 Luna execution brief — canonical incident containment

You are the GPT-5.6 Luna execution owner for task T0.0 in:

`/Users/peteromalley/Documents/Arnold/docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`

Work from the live repository and external state, not prior narrative. Read the
entire T0.0 task, the task-list evidence rules, the binding M11 brief at
`.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md`,
and the current delegation/authority contracts under
`/private/tmp/arnold-post-c7-release-recovery/arnold_pipelines/megaplan/`.

Goal: complete T0.0, not merely analyze it. Resolve and record the exact
canonical Run Authority containment interface and append/obtain the authoritative
containment decision for the poisoned Critique Ledger tuple. The exact incident
identity includes session `critique-ledger-accountability-v2-20260728`, plan
`cl2-wbc-backed-ledger-20260731-1411`, and the v2 selection/spec/workspace/branch/runtime
coordinates you must derive from authoritative evidence.

Hard constraints:

- The current `megaplan-cloud` skill is explicitly zero-authority history under
  M11. Do not materialize legacy `cloud chain --fresh`, raw `chain start`, tmux,
  marker edits, watchdog, direct launcher, or shell-side mutation.
- Read-only local/cloud inspection is allowed. A cloud mutation is allowed only
  through a current, named Run Authority owner interface whose grant/fence/CAS
  semantics you can prove from installed code and authoritative records.
- Do not invent an interface or treat user prose as a synthetic Run Authority
  receipt. If the interface genuinely does not exist or cannot issue this
  decision, prove that precisely and implement the smallest fail-closed owner
  interface needed for T0.0 in an isolated clean worktree, with tests and a
  handoff; do not mutate production through an unaccepted build.
- The main checkout is heavily dirty with other users/agents' work. Preserve it.
  Use isolated worktrees for code mutations. For evidence/task-board edits in
  this checkout, use `apply_patch`; do not overwrite unrelated content.
- Never reveal secrets. Never perform destructive cleanup.

Required deliverables under
`/Users/peteromalley/Documents/Arnold/evidence/critique-ledger-recovery/T0.0/`:

1. `authority-interface.md`: exact owner, command/API, installed source revision,
   inputs, outputs, grant/fence/CAS behavior, and why it is authoritative.
2. `containment-decision.json`: the actual owner-issued decision/receipt if it can
   be issued safely now; otherwise a machine-readable `status=blocked` record with
   the exact missing owner capability and strongest evidence.
3. `source-manifest.json`: content-addressed references for every decisive local
   or remote claim (path/URI, SHA-256, size, capture time, collector/tool/version,
   runtime/commit, clock basis, minimal query/excerpt).
4. `completion-manifest.json`: signed or cryptographically digested manifest
   enumerating all required claims, artifacts, hashes, commands, exit codes,
   timestamps, owner/interface, authority receipt, and a truthful verdict.
5. `handoff.md`: concise conclusion and the exact next executable action for T0.1.

If T0.0 is fully proven, update only its checkbox/status plus the single
`Current next action` line in the plan using `apply_patch`. If it remains blocked,
do not check it off and do not claim completion.

Return a concise final report naming the authoritative interface, whether the
containment decision was actually recorded, evidence paths, mutations performed,
tests run, and any exact blocker. Do not stop at recommendations while safe,
in-scope progress remains.
