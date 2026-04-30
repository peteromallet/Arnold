# Sprint 1c Attachments Deferrals

This note captures attachment work intentionally left out of Sprint 1b.

- Invocation-mode attachments remain deferred: CLI `--attach`, Python `run_turn(attachments=...)`, and `LocalBlobStore` for caller-uploaded files.
- A dedicated `transcribe_voice` tool and the non-voice-audio path remain deferred.
- Voice/image ingestion crash-before-upload plus Discord URL expiry results in orphaned ledger rows. The persisted inbound message prevents silent data loss; manual user re-send is the recovery path. A future sprint may add an ingestion-time bytes-to-tmpfile fallback if the orphaned rate is meaningful.
