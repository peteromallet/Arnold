"""Arnold runtime — neutral carrier types for capability operations and execution.

This sub-package defines the pure-data, opinion-free contracts that let
Arnold dispatch plugin-owned operations without importing or referencing
Megaplan policy, phase names, gate labels, override vocabularies, profile
semantics, or artifact conventions.

The public package surface is intentionally minimal.  Internal callers should
import from the relevant submodule (``arnold.runtime.driver``,
``arnold.runtime.state_persistence``, etc.) rather than relying on broad
package re-exports.

Sub-modules (landed incrementally across M2a, M3d and M8 tasks):
* ``envelope``         — ``RuntimeEnvelope``, the runtime-owned run envelope.
* ``resume``           — ``ResumeCursor`` and legacy-resume migration contract.
* ``operations``       — ``OperationRequest`` / ``OperationResult`` carriers.
* ``driver``           — ``StepwiseDriver`` Protocol and ``IsolationMode``.
* ``settings``         — Runtime settings shape and ``EffectiveSetting``.
* ``settings_resolver`` — Precedence-chain resolver and ``ResolvedSettings``.
* ``dry_run``          — ``--dry-run`` CLI entrypoint (proof harness).
* ``batch``            — Neutral batch carriers (BatchUnit, BatchRunResult, …).
* ``batch_settings``   — Batch-runtime settings normalization.
* ``recovery``         — Neutral recovery-classifier seam (Protocol +
                        ``NullRecoveryPolicy``).
* ``oracle``           — ``OracleResult`` + ``run`` typed subprocess seam.
* ``state_persistence`` — ``plan_state_lock``, ``atomic_write_bytes``,
                         ``atomic_write_text``, ``atomic_write_json``.
* ``event_journal``    — ``EventEnvelope``, ``EventSink`` Protocol,
                         ``NdjsonEventJournal``, ``NdjsonEventSink``.
* ``effect``           — ``Effect`` dataclass, ``ReplayClass`` enum,
                         ``NONCOMPENSABLE`` sentinel.
* ``wal_fold``         — ``fold_journal`` parameterized fold combinator,
                         ``last_state_snapshot_projector``, and
                         ``read_event_journal`` re-export.
* ``semantic_replay``  — ``semantic_equivalent`` deep structural
                         comparison with dotted-path ignore/unordered
                         support, and ``semantic_replay_journal`` for
                         journal replay with equivalence checking.
* ``CONTRACT.md``      — Human-readable contract documentation.

Boundary contract
-----------------

**Zero Megaplan imports.** No source file under ``arnold/runtime/`` may
contain ``import megaplan`` or ``from megaplan``.  This is enforced by
an AST-level boundary test at ``tests/arnold/runtime/test_package_boundary.py``.

**Zero Megaplan vocabulary.** No Megaplan phase names (``planning``,
``critique``, ``finalize``, ``tiebreaker``, ``escalate``), override
actions (``force_proceed``, ``abort``, ``replan``, ``add_note``), or
gate labels may appear as string literals in ``arnold/runtime/`` source.

**Neutral naming.** Arnold owns only runtime-neutral names: run envelope,
operation carriers, isolation modes, and settings; Megaplan supplies
defaults, policy interpretation, and argument translation for its phases.

Import from ``arnold.runtime``:

    from arnold.runtime import RuntimeEnvelope, RunOutcome, OracleResult
    from arnold.runtime.event_journal import read_event_journal

No Megaplan re-exports appear here; this is the neutral surface.
"""

# Re-export boundary-guard metadata so the AST-scan test can verify
# the package is self-describing about its contract.
from arnold.runtime import oracle  # noqa: F401 — make the oracle module accessible as arnold.runtime.oracle
from arnold.runtime.envelope import RunContext, RunEnvelope, RuntimeEnvelope
from arnold.runtime.errors import ArnoldError
from arnold.runtime.oracle import OracleResult, run as oracle_run
from arnold.runtime.outcome import RunOutcome, RunResultMetadata
from arnold.runtime.effect import NONCOMPENSABLE, Effect, ReplayClass  # noqa: F401 — re-export for convenience
from arnold.runtime.event_journal import (  # noqa: F401 — re-export for convenience
    EventEnvelope,
    EventSink,
    NdjsonEventJournal,
    NdjsonEventSink,
    read_event_journal,
    read_event_journal_paged,
    stream_event_journal,
)
from arnold.runtime.semantic_replay import (  # noqa: F401 — re-export for convenience
    semantic_equivalent,
    semantic_replay_journal,
)
from arnold.runtime.wal_fold import (  # noqa: F401 — re-export for convenience
    fold_journal,
    last_state_snapshot_projector,
)

__all__: list[str] = [
    "ArnoldError",
    "Effect",
    "EventEnvelope",
    "EventSink",
    "NdjsonEventJournal",
    "NdjsonEventSink",
    "NONCOMPENSABLE",
    "OracleResult",
    "ReplayClass",
    "RunContext",
    "RunEnvelope",
    "RuntimeEnvelope",
    "RunOutcome",
    "RunResultMetadata",
    "fold_journal",
    "last_state_snapshot_projector",
    "oracle_run",
    "read_event_journal",
    "read_event_journal_paged",
    "stream_event_journal",
    "semantic_equivalent",
    "semantic_replay_journal",
]
