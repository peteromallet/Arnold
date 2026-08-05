"""Durable owner boundary for the generic authority contracts."""

# Keep the contract module free of storage policy.  This small public facade
# gives callers one stable import while the owner adapter lives beside the
# package rather than inside its persistence-neutral core.
from arnold_pipelines.run_authority_store import (
    AppendResult,
    AuthorityJournalError,
    AuthorityRecord,
    GLEKConflictError,
    InvalidAuthorityRecordError,
    InvalidCursorError,
    JournalCommitIndeterminateError,
    JournalCorruptionError,
    JournalStorageError,
    JournalView,
    RunAuthorityJournal,
    StaleCursorError,
    IdempotencyConflictError,
    derive_glek,
)

__all__ = [
    "AppendResult",
    "AuthorityJournalError",
    "AuthorityRecord",
    "GLEKConflictError",
    "InvalidAuthorityRecordError",
    "InvalidCursorError",
    "JournalCommitIndeterminateError",
    "JournalCorruptionError",
    "JournalStorageError",
    "JournalView",
    "RunAuthorityJournal",
    "StaleCursorError",
    "IdempotencyConflictError",
    "derive_glek",
]
