"""Arnold runtime — neutral carrier types for capability operations and execution.

This sub-package defines the pure-data, opinion-free contracts that let
Arnold dispatch plugin-owned operations without importing or referencing
Megaplan policy, phase names, gate labels, override vocabularies, profile
semantics, or artifact conventions.

Sub-modules (landed incrementally across M2a tasks):
* ``envelope``         — ``RuntimeEnvelope``, the runtime-owned run envelope.
* ``resume``           — ``ResumeCursor`` and legacy-resume migration contract.
* ``operations``       — ``OperationRequest`` / ``OperationResult`` carriers.
* ``driver``           — ``StepwiseDriver`` Protocol and ``IsolationMode``.
* ``settings``         — Runtime settings shape and ``EffectiveSetting``.
* ``settings_resolver`` — Precedence-chain resolver and ``ResolvedSettings``.
* ``dry_run``          — ``--dry-run`` CLI entrypoint (proof harness).
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

    from arnold.runtime import RuntimeEnvelope, OperationRequest, StepwiseDriver

No Megaplan re-exports appear here; this is the neutral surface.
"""

# Re-export boundary-guard metadata so the AST-scan test can verify
# the package is self-describing about its contract.
__all__: list[str] = []
