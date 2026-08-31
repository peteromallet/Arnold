# Luna review brief — Batch 3 NBF-04 attempt 3

Review the cumulative NBF-04 candidate at checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`. Bind to the attempt2 packet SHA
`61d85b9f6d6d8fde4069df9d63c89f9c728d5562ba1e80e04dc7c76a0d901ece`, attempt2
review brief SHA `cf87109c74dd37074fece2c3fb618df9fe07a53ab70053bfa0e1100c265383cb`,
Batch3 execution brief SHA `1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`,
and the frozen hashes listed in the attempt3 packet.

Judge NBF-04 only. Verify record-before-signal, distinct TERM/KILL confirmation
IDs, dynamic same-incarnation rereads and PID-reuse rejection, already-dead
handling, exactly-once disposition/terminal append, replay without resignal,
strict missing-context holds, and terminal reconciliation. Verify actual native,
OMP, managed, handler, launcher, fan, resident, operator, orphan, and timeout
paths use the existing WBC/disposition authority; child certification must not
create a second WBC/admission authority. Confirm no worker raw signal/fallback
remains outside the canonical doors and that native control reaches the installed
signal ladder. The resident contextless transient Codex process is a generic
non-worker process-group path and must not weaken managed-worker strictness.

Use the exact test outcomes and the three remaining static/fixture risks in
`.oracle/rework/batch-3-nbf04-attempt-3.md`. Do not expand into NBF05/06,
generated inventory redesign, unrelated fixture migration, status or execution
log changes, frozen artifacts, commit/push/merge/deploy, or dependency installs.
The reviewed source/test manifest SHA is
`13ac3bdb09658124a526bc3d9100257cab54a0dbcca6a53e5d577607c74443e3`; full
binary diff SHA is
`0d54a97670986c4f298090c53755f1b2fd348fd643013cc84078d34dda3fda12`.
