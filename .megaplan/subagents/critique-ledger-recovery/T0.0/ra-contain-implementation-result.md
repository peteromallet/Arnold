# T0.0 RA-CONTAIN implementation handoff

Follow-up repair commit: `0b757880ea25ff75afc2a701c920c38f18385568` (`Repair RA-CONTAIN owner contract`), based on `6a4be1aa2b6e31587802402c1602f18430840478`.

The owner journal now uses CAS `(cursor, owner_revision)` with genesis `(0, 64 zeroes)`, validates both values before issue/terminate, and derives receipts from replayed authoritative state. Replay is strict about operations, transitions, receipt content hashes, record hashes, duplicate identity, and malformed records. The exact tuple is exactly seven required non-empty scalar strings. Policy denies `resume`, `repair`, `execute`, `publish`, `notify`, and `deployment`, while allowing `observe`; `check` reads the journal and returns a typed result. Missing, inactive, expired, mismatched, fabricated, or corrupt authority refuses closed.

CLI: `python -m arnold_pipelines.run_authority.containment --journal PATH {status|issue|terminate|check}`. Successful operations exit 0; expected contract/storage/JSON/action failures emit stable JSON `{ok:false,code,error}` and exit 2. Owner-local locking, append-only records, fsync, and directory fsync remain in place. Torn journals are not repaired or claimed repaired.

Validation run in the task worktree:

- `pytest -q tests/arnold_pipelines/run_authority tests/test_pipeline_run_cli.py` — 74 passed.
- Focused containment: `pytest -q tests/arnold_pipelines/run_authority/test_containment.py` — 6 passed.
- Unknown action CLI probe — exit 2, JSON refusal, no traceback.
- `git diff --check` — passed before commit.

Changed files: `arnold_pipelines/run_authority/containment.py`, `arnold_pipelines/run_authority/__init__.py`, and `tests/arnold_pipelines/run_authority/test_containment.py`.

No push, deployment, or cloud mutation performed. Remaining acceptance work is binding downstream effect boundaries to the authoritative policy API and any deployment-specific acceptance outside this local owner interface.

## GPT-5.6 Luna repair pass 2

Follow-up commit: `eaeca1e7d97deb93ecbdd0f68930001f9f810d84` (`Close RA-CONTAIN pass-2 failure paths`), based on `0b757880ea25ff75afc2a701c920c38f18385568`.

Closed the pass-2 blockers: owner-local lock/journal/directory open, append, fsync, and close failures now become typed `StorageError` containment refusals; finite positive non-boolean TTL validation occurs before decision-id hashing; subprocess race coverage proves identical duplicates converge to one issue record while divergent losers receive stale CAS and cannot create a second accepted decision; restart coverage preserves issue and termination records/state/digest; CLI invalid-TTL and no-traceback coverage was added. Test fixtures remain confined to pytest `tmp_path` directories.

Exact validation from the repair worktree:

- `for n in 1 2 3; do pytest -q tests/arnold_pipelines/run_authority/test_containment.py || exit; done` — 15 passed each run.
- `pytest -q tests/arnold_pipelines/run_authority tests/run_authority tests/test_pipeline_run_cli.py tests/cloud/test_m1_containment_acceptance.py` — 105 passed.
- `git diff --check` — passed.

No push, deployment, or cloud mutation performed.
