# B12 — Live Astrid end-to-end flow evidence

Date: 2026-08-10 (session) — Arnold HEAD (pre-B12 commit), Astrid repo at
`/workspace/omp-replaces-hermes/Astrid`.

## Environment

- Astrid repo: `/workspace/omp-replaces-hermes/Astrid` (no `.git`; sibling
  worktree of the Arnold migration checkout).
- Interpreter: `/workspace/omp-replaces-hermes/.venv/bin/python` (editable
  `arnold` + `astrid` import path).
- Astrid host adapter requires the migrated Arnold package; two Astrid-side
  adaptations were needed to satisfy the migrated public API:

  1. `host/envelope.py` — `CrossCutting.retry_budget` is an `int` in the
     migrated Arnold (was a dict); the Astrid projection now passes it
     through.
  2. `host/cli.py` — migrated `StepContext.__init__` requires
     `artifact_root` + `state`; `_make_human_resume_cursor` now supplies
     them.
  3. `host/compat.py` — migrated `persist_resume_cursor` takes
     `(artifact_root, *, stage, resume_cursor)` and `read_resume_cursor`
     returns the raw payload dict; Astrid compat adapters round-trip the
     `ResumeCursorRef` object through the new API (incl. JSON-encoding the
     embedded `StepContext` dataclass).
  4. `host/render.py` — the terminal `halt` control stage is rendered as
     "Run complete. Nothing to acknowledge." instead of an un-routable ack.

## Resident attach (identity bootstrap)

The gateway requires an agent identity; the attach contract is `agent:<id>`.
The identity validator only accepts slugs (no `:`), so the on-disk identity
carries the slug `b12live` and the session binds to the project:

```
astrid projects create b12-live            -> created (projects/b12-live)
astrid attach b12-live                     -> timeline: (none) run: (none) role: writer
```

## Gateway loop: start -> next -> action -> ack

```
astrid start --engine arnold --project b12-live --workflow text_analysis.summarize
  -> started text_analysis.summarize  run-id: arnold-8a8177a8c8af
     plan-hash: fb31cbc1...

astrid next --engine arnold --project b12-live
  -> stage: Read Input (read_input)  ready for acknowledgement:
     astrid ack --engine arnold --project b12-live --stage read_input --decision approve|reject

astrid ack --engine arnold --project b12-live --stage read_input --decision approve
  -> acknowledged Arnold stage for project b12-live
```

Every stage exposes exactly one legal action (the ack command); the resident
executes the stage's `task.local` invocation (writing into
`<run-root>/<stage>/v1/produces`) and then acks with `--produces-artifact` +
`--produces-input` re-verification:

```
# write_summary stage invocation -> summary.json
astrid ack --engine arnold --project b12-live --stage write_summary --decision approve \
  --produces-artifact .../write_summary/v1/produces/summary.json --produces-input word_count=...

astrid ack --engine arnold --project b12-live --stage write_verdict --decision approve \
  --produces-artifact .../write_verdict/v1/produces/verdict.json

astrid next -> stage: Halt (halt)  Run complete. Nothing to acknowledge.
```

Final run status: `arnold_run.json` `status: completed`; feedback ledger
records all three approvals (`read_input`, `write_summary`, `write_verdict`).

## Artifacts produced (run dir)

```
projects/b12-live/runs/arnold-8a8177a8c8af/
  arnold_run.json  events.jsonl  lease.json  pipeline.json  resume_cursor.json  state.json
  read_input/v1/produces/content.json
  write_summary/v1/produces/summary.json
  write_verdict/v1/produces/verdict.json
```

The persisted `resume_cursor.json` round-trips through the migrated
`persist_resume_cursor`/`read_resume_cursor` API (stage + embedded
`ResumeCursorRef` JSON).

## Typed media + MediaUsage evidence (resident store)

The resident evidence emitter (`resident/media_evidence.py`) records typed
media artifacts (`video/mp4`, `audio/wav`, `x-astrid-timeline`) plus their
`MediaUsage` cost entries into the resident store. Covered by
`tests/resident/test_astrid_resident.py::test_emit_media_evidence_records_evidence_and_cost`
(evidence + cost system-log records with digest, producer tool, run id, stage,
and the `timeline_document`/`video_second`/`audio_second` unit mapping).

## Generator + checked-in contracts

`resident generate astrid` emits the four contracts; the checked-in
`examples/agents/astrid-resident.md` and `examples/resident/astrid/*.yaml`
match the generator output byte-for-byte (`test_checked_in_astrid_*`).
Project-scope install writes `.omp/agents/` (shadows user scope).
