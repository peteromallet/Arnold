Implemented and committed the RA-CONTAIN repair.

- Commit: `0b757880ea25ff75afc2a701c920c38f18385568`
- Tests: 74 passed
- Focused containment tests: 6 passed
- `git diff --check`: passed
- Handoff updated: `ra-contain-implementation-result.md`

Implemented strict `(cursor, owner_revision)` CAS, exact tuple validation, six-effect denial including deployment, authoritative `check` API/CLI, strict replay integrity, typed JSON failures, expiry/termination handling, and append-only fsync-safe journaling.

No push, deployment, or cloud mutation performed.